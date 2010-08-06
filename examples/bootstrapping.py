# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
Using SPM for analysis
=======================

The spm_tutorial.py integrates several interfaces to perform a first
and second level analysis on a two-subject data set.  The tutorial can
be found in the examples folder.  Run the tutorial from inside the
nipype tutorial directory:

    python spm_tutorial.py

"""
from copy import deepcopy


"""Import necessary modules from nipype."""

import nipype.interfaces.io as nio           # Data i/o
import nipype.interfaces.spm as spm          # spm
import nipype.interfaces.matlab as mlab      # how to run matlab
import nipype.interfaces.fsl as fsl          # fsl
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
import nipype.algorithms.rapidart as ra      # artifact detection
import nipype.algorithms.modelgen as model   # model specification
import nipype.algorithms.misc as misc
import os                                    # system functions

"""

Preliminaries
-------------

Confirm package dependencies are installed.  (This is only for the
tutorial, rarely would you put this in your own code.)
"""

from nipype.utils.misc import package_check

package_check('numpy', '1.3', 'tutorial1')
package_check('scipy', '0.7', 'tutorial1')
package_check('networkx', '1.0', 'tutorial1')
package_check('IPython', '0.10', 'tutorial1')

"""Set any package specific configuration. The output file format
for FSL routines is being set to uncompressed NIFTI and a specific
version of matlab is being used. The uncompressed format is required
because SPM does not handle compressed NIFTI.
"""

# Tell fsl to generate all output in uncompressed nifti format
#print fsl.Info.version()
fsl.FSLCommand.set_default_output_type('NIFTI')

# Set the way matlab should be called
mlab.MatlabCommand.set_default_matlab_cmd("matlab -nodesktop -nosplash")

"""The nipype tutorial contains data for two subjects.  Subject data
is in two subdirectories, ``s1`` and ``s2``.  Each subject directory
contains four functional volumes: f3.nii, f5.nii, f7.nii, f10.nii. And
one anatomical volume named struct.nii.

Below we set some variables to inform the ``datasource`` about the
layout of our data.  We specify the location of the data, the subject
sub-directories and a dictionary that maps each run to a mnemonic (or
field) for the run type (``struct`` or ``func``).  These fields become
the output fields of the ``datasource`` node in the pipeline.

In the example below, run 'f3' is of type 'func' and gets mapped to a
nifti filename through a template '%s.nii'. So 'f3' would become
'f3.nii'.

"""

# Specify the location of the data.
data_dir = os.path.abspath('data')
# Specify the subject directories
subject_list = ['s1']
# Map field names to individual subject runs.
info = dict(func=[['subject_id', ['f3','f5','f7','f10']]],
            struct=[['subject_id','struct']])

infosource = pe.Node(interface=util.IdentityInterface(fields=['subject_id']),
                     name="infosource")

"""Here we set up iteration over all the subjects. The following line
is a particular example of the flexibility of the system.  The
``datasource`` attribute ``iterables`` tells the pipeline engine that
it should repeat the analysis on each of the items in the
``subject_list``. In the current example, the entire first level
preprocessing and estimation will be repeated for each subject
contained in subject_list.
"""

infosource.iterables = ('subject_id', subject_list)

"""
Preprocessing pipeline nodes
----------------------------

Now we create a :class:`nipype.interfaces.io.DataSource` object and
fill in the information from above about the layout of our data.  The
:class:`nipype.pipeline.NodeWrapper` module wraps the interface object
and provides additional housekeeping and pipeline specific
functionality.
"""

datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                               outfields=['func', 'struct']),
                     name = 'datasource')
datasource.inputs.base_directory = data_dir
datasource.inputs.template = '%s/%s.nii'
datasource.inputs.template_args = info


"""Use :class:`nipype.interfaces.spm.Realign` for motion correction
and register all images to the mean image.
"""

realign = pe.Node(interface=spm.Realign(), name="realign")
realign.inputs.register_to_mean = True

"""Use :class:`nipype.algorithms.rapidart` to determine which of the
images in the functional series are outliers based on deviations in
intensity or movement.
"""

art = pe.Node(interface=ra.ArtifactDetect(), name="art")
art.inputs.use_differences      = [True,True]
art.inputs.use_norm             = True
art.inputs.norm_threshold       = 0.5
art.inputs.zintensity_threshold = 3
art.inputs.mask_type            = 'spm_global'
art.inputs.parameter_source     = 'SPM'


"""Use :class:`nipype.interfaces.spm.Coregister` to perform a rigid
body registration of the functional data to the structural data.
"""

coregister = pe.Node(interface=spm.Coregister(), name="coregister")
coregister.inputs.jobtype = 'estimate'


"""Smooth the functional data using
:class:`nipype.interfaces.spm.Smooth`.
"""

smooth = pe.Node(interface=spm.Smooth(fwhm = 4), name = "smooth")

"""
Set up analysis components
--------------------------

Here we create a function that returns subject-specific information
about the experimental paradigm. This is used by the
:class:`nipype.interfaces.spm.SpecifyModel` to create the information
necessary to generate an SPM design matrix. In this tutorial, the same
paradigm was used for every participant.
"""

from nipype.interfaces.base import Bunch

names = ['Task-Odd','Task-Even']
onsets = [[],[]]
for r in range(4):
    onsets[0] += range(5 + r*85,80+r*85,20)
    onsets[1] += range(15 + r*85,80+r*85,20)
subjectinfo = [Bunch(conditions=names,
                    onsets=onsets,
                    durations=[[5] for s in names],
                    amplitudes=None,
                    tmod=None,
                    pmod=None,
                    regressor_names=None,
                    regressors=None)]

subjectinfo_empty = [Bunch(conditions=[],
                        onsets=[],
                        durations=[],
                        amplitudes=None,
                        tmod=None,
                        pmod=None,
                        regressor_names=None,
                        regressors=None) for _ in range(4)]

"""Setup the contrast structure that needs to be evaluated. This is a
list of lists. The inner list specifies the contrasts and has the
following format - [Name,Stat,[list of condition names],[weights on
those conditions]. The condition names must match the `names` listed
in the `subjectinfo` function described above.
"""

cont1 = ('Task>Baseline','T', ['Task-Odd','Task-Even'],[0.5,0.5])
cont2 = ('Task-Odd>Task-Even','T', ['Task-Odd','Task-Even'],[1,-1])
contrasts = [cont1,cont2]

"""Generate SPM-specific design information using
:class:`nipype.interfaces.spm.SpecifyModel`.
"""

modelspec_detrend = pe.Node(interface=model.SpecifyModel(), name= "modelspec_detrend")
modelspec_detrend.inputs.concatenate_runs        = True
modelspec_detrend.inputs.input_units             = 'secs'
modelspec_detrend.inputs.output_units            = 'secs'
modelspec_detrend.inputs.time_repetition         = 3.
modelspec_detrend.inputs.high_pass_filter_cutoff = 120
modelspec_detrend.inputs.subject_info            = subjectinfo_empty

"""Generate a first level SPM.mat file for analysis
:class:`nipype.interfaces.spm.Level1Design`.
"""

level1design_detrend = pe.Node(interface=spm.Level1Design(), name= "level1design_detrend")
level1design_detrend.inputs.timing_units       = modelspec_detrend.inputs.output_units
level1design_detrend.inputs.interscan_interval = modelspec_detrend.inputs.time_repetition
level1design_detrend.inputs.bases              = {'hrf':{'derivs': [0,0]}}


"""Use :class:`nipype.interfaces.spm.EstimateModel` to determine the
parameters of the model.
"""

level1estimate_detrend = pe.Node(interface=spm.EstimateModel(), name="level1estimate_detrend")
level1estimate_detrend.inputs.estimation_method = {'Classical' : 1}
level1estimate_detrend.inputs.save_residual_images = True

join_residuals = pe.Node(interface=fsl.Merge(dimension="t"), name="join_residuals")


# from float64 to float32
img2float = pe.Node(interface=fsl.ImageMaths(out_data_type='float',
                                             op_string = '',
                                             suffix='_dtype'),
                       name='img2float')

"""Generate SPM-specific design information using
:class:`nipype.interfaces.spm.SpecifyModel`.
"""

modelspec = pe.Node(interface=model.SpecifyModel(), name= "modelspec")
modelspec.inputs.input_units             = 'scans'
modelspec.inputs.output_units            = 'scans'
modelspec.inputs.time_repetition         = 3.
modelspec.inputs.subject_info    = subjectinfo

"""Generate a first level SPM.mat file for analysis
:class:`nipype.interfaces.spm.Level1Design`.
"""

level1design = pe.Node(interface=spm.Level1Design(), name= "level1design")
level1design.inputs.timing_units       = modelspec.inputs.output_units
level1design.inputs.interscan_interval = modelspec.inputs.time_repetition
level1design.inputs.bases              = {'hrf':{'derivs': [0,0]}}


"""Use :class:`nipype.interfaces.spm.EstimateModel` to determine the
parameters of the model.
"""

level1estimate = pe.Node(interface=spm.EstimateModel(), name="level1estimate")
level1estimate.inputs.estimation_method = {'Classical' : 1}


"""Use :class:`nipype.interfaces.spm.EstimateContrast` to estimate the
first level contrasts specified in a few steps above.
"""

contrastestimate = pe.Node(interface = spm.EstimateContrast(), name="contrastestimate")
contrastestimate.inputs.contrasts = contrasts

threshold = pe.Node(interface=spm.Threshold(contrast_index=1, use_fwe_correction = False), name="threshold")

bootstrap = pe.Node(interface=misc.BootstrapTimeSeries(), name="bootstrap")
bootstrap.inputs.blocks_info = Bunch(onsets = subjectinfo[0].onsets, duration = [10, 10])
id = range(100)
bootstrap.iterables = ('id',id)

"""
Setup the pipeline
------------------

The nodes created above do not describe the flow of data. They merely
describe the parameters used for each function. In this section we
setup the connections between the nodes such that appropriate outputs
from nodes are piped into appropriate inputs of other nodes.

Use the :class:`nipype.pipeline.engine.Pipeline` to create a
graph-based execution pipeline for first level analysis. The config
options tells the pipeline engine to use `workdir` as the disk
location to use when running the processes and keeping their
outputs. The `use_parameterized_dirs` tells the engine to create
sub-directories under `workdir` corresponding to the iterables in the
pipeline. Thus for this pipeline there will be subject specific
sub-directories.

The ``nipype.pipeline.engine.Pipeline.connect`` function creates the
links between the processes, i.e., how data should flow in and out of
the processing nodes.
"""

l1pipeline = pe.Workflow(name="level1")
l1pipeline.base_dir = os.path.abspath('bootstrapping/workingdir')

l1pipeline.connect([(infosource, datasource, [('subject_id', 'subject_id')]),
                  (datasource,realign,[('func','in_files')]),
                  (realign,coregister,[('mean_image', 'source'),
                                       ('realigned_files','apply_to_files')]),
        		  (datasource,coregister,[('struct', 'target')]),
                  (coregister,smooth, [('coregistered_files', 'in_files')]),
                  (infosource,modelspec_detrend,[('subject_id','subject_id')]),
                  (realign,modelspec_detrend,[('realignment_parameters','realignment_parameters')]),
                  (realign,art,[('realignment_parameters','realignment_parameters')]),
                  (coregister,art,[('coregistered_files','realigned_files')]),
                  (art,modelspec_detrend,[('outlier_files','outlier_files')]),
                  (smooth,modelspec_detrend,[('smoothed_files','functional_runs')]),                  
                  (modelspec_detrend,level1design_detrend,[('session_info','session_info')]),
                  (level1design_detrend,level1estimate_detrend,[('spm_mat_file','spm_mat_file')]),
                  (level1estimate_detrend, join_residuals, [('residual_images', 'in_files')]),
                  (join_residuals, img2float, [('merged_file', 'in_file')]),
                  
                  (img2float, bootstrap, [('out_file', 'original_volume')]),
                  
                  (bootstrap, modelspec, [('bootstraped_volume', 'functional_runs')]),
#                  (join_residuals, modelspec, [('merged_file', 'functional_runs')]),
                  (infosource,modelspec,[('subject_id','subject_id')]),
                  (modelspec,level1design,[('session_info','session_info')]),
                  (level1estimate_detrend, level1design, [('mask_image', 'mask_image')]),
                  (level1design,level1estimate,[('spm_mat_file','spm_mat_file')]),
                  (level1estimate,contrastestimate,[('spm_mat_file','spm_mat_file'),
                                                  ('beta_images','beta_images'),
                                                  ('mean_residual_image','mean_residual_image')]),                                               
                  (contrastestimate, threshold,[('spm_mat_file','spm_mat_file'),
                                                  ('spmT_images', 'spmT_images')]),
                  (level1estimate, threshold,[('RPVimage', 'RPVimage'),
                                                ('mask_image','mask_image'),
                                                ('beta_images','beta_images'),
                                                ('mean_residual_image','mean_residual_image')])
                  ])





l2pipeline = pe.Workflow(name="level2")
l2pipeline.base_dir = os.path.abspath('bootstrapping/workingdir')

l2source = pe.Node(nio.DataGrabber(infields=["subject_id", "id"]),name="l2source")
l2source.inputs.template=os.path.abspath('bootstrapping/workingdir/level1/_subject_id_%s/_id_%d/threshold/thresholded_map.img')
l2source.inputs.id = id
l2source.iterables = [('subject_id',subject_list)]
frequency_map = pe.Node(misc.FrequencyMap(), name="frequency_map")

l2pipeline.connect([
                    (l2source,frequency_map, [('outfiles', 'binary_images')])
                    ])

"""
Execute the pipeline
--------------------

The code discussed above sets up all the necessary data structures
with appropriate parameters and the connectivity between the
processes, but does not generate any output. To actually run the
analysis on the data the ``nipype.pipeline.engine.Pipeline.Run``
function needs to be called.
"""

if __name__ == '__main__':
    l1pipeline.run()
    l2pipeline.write_graph()
    l2pipeline.run()
