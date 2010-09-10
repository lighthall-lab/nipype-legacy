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
from nipype.interfaces.base import Bunch


"""Import necessary modules from nipype."""

import nipype.interfaces.io as nio           # Data i/o
import nipype.interfaces.spm as spm          # spm
import nipype.interfaces.fsl as fsl          # fsl
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
import nipype.algorithms.rapidart as ra      # artifact detection
import nipype.algorithms.modelgen as model   # model specification
import nipype.algorithms.misc as misc
import os                                    # system functions


preproc_pipeline = pe.Workflow(name="preproc")

realign = pe.Node(interface=spm.Realign(), name="realign")
realign.inputs.register_to_mean = True

art = pe.Node(interface=ra.ArtifactDetect(), name="art")
art.inputs.use_differences      = [True,True]
art.inputs.use_norm             = True
art.inputs.norm_threshold       = 0.5
art.inputs.zintensity_threshold = 3
art.inputs.mask_type            = 'spm_global'
art.inputs.parameter_source     = 'SPM'

coregister = pe.Node(interface=spm.Coregister(), name="coregister")
coregister.inputs.jobtype = 'estimate'

smooth = pe.Node(interface=spm.Smooth(fwhm = 4), name = "smooth")

preproc_pipeline.connect([(realign, coregister, [('mean_image', 'source'),
                                                 ('realigned_files', 'apply_to_files')]),
                          (coregister, smooth, [('coregistered_files', 'in_files')]),
                          (realign, art, [('realignment_parameters', 'realignment_parameters')]),
                          (coregister, art, [('coregistered_files', 'realigned_files')])])


detrend_pipeline = pe.Workflow(name="detrend")



modelspec_detrend = pe.Node(interface=model.SpecifyModel(), name= "modelspecd")

level1design_detrend = pe.Node(interface=spm.Level1Design(), name= "level1designd")
level1design_detrend.inputs.bases              = {'hrf':{'derivs': [0,0]}}
level1design_detrend.inputs.model_serial_correlations = "AR(1)"

level1estimate_detrend = pe.Node(interface=spm.EstimateModel(), name="level1estimated")
level1estimate_detrend.inputs.estimation_method = {'Classical' : 1}
level1estimate_detrend.inputs.save_residual_images = True

join_residuals = pe.Node(interface=fsl.Merge(dimension="t"), name="join_residuals")

# from float64 to float32
img2float = pe.Node(interface=fsl.ImageMaths(), name='img2float')
img2float.inputs.out_data_type = 'float'
img2float.inputs.op_string = ''
img2float.inputs.suffix = '_dtype'

#detrend_pipeline.connect([(modelspec_detrend,level1design_detrend,[('session_info','session_info')]),
#                          (level1design_detrend,level1estimate_detrend,[('spm_mat_file','spm_mat_file')]),
#                          (level1estimate_detrend, join_residuals, [('residual_images', 'in_files')]),
#                          (join_residuals, img2float, [('merged_file', 'in_file')])])

analysis_pipeline = pe.Workflow(name="analysis")

modelspec = pe.Node(interface=model.SpecifyModel(), name= "modelspec")

level1design = pe.Node(interface=spm.Level1Design(), name= "level1design")
level1design.inputs.bases              = {'hrf':{'derivs': [0,0]}}
level1design_detrend.inputs.model_serial_correlations = "none"

level1estimate = pe.Node(interface=spm.EstimateModel(), name="level1estimate")
level1estimate.inputs.estimation_method = {'Classical' : 1}

contrastestimate = pe.Node(interface = spm.EstimateContrast(), name="contrastestimate")

threshold = pe.Node(interface=spm.Threshold(), name="threshold")

analysis_pipeline.connect([(modelspec,level1design,[('session_info','session_info')]),
                  
                  (level1design,level1estimate,[('spm_mat_file','spm_mat_file')]),
                  (level1estimate,contrastestimate,[('spm_mat_file','spm_mat_file'),
                                                  ('beta_images','beta_images'),
                                                  ('mean_residual_image','mean_residual_image')]),                                               
                  (contrastestimate, threshold,[('spm_mat_file','spm_mat_file'),
                                                  ('spmT_images', 'spmT_images')]),
                  (level1estimate, threshold,[('RPVimage', 'RPVimage'),
                                                ('mask_image','mask_image'),
                                                ('beta_images','beta_images'),
                                                ('mean_residual_image','mean_residual_image')])])


# Specify the location of the data.
data_dir = os.path.abspath('data')
# Specify the subject directories
subject_list = ['s1']
# Map field names to individual subject runs.
info = dict(func=[['subject_id', ['f3','f5','f7','f10']]],
            struct=[['subject_id','struct']])

infosource = pe.Node(interface=util.IdentityInterface(fields=['subject_id']),
                     name="infosource")

infosource.iterables = ('subject_id', subject_list)

datasource = pe.Node(interface=nio.DataGrabber(infields=['subject_id'],
                                               outfields=['func', 'struct']),
                     name = 'datasource')
datasource.inputs.base_directory = data_dir
datasource.inputs.template = '%s/%s.nii'
datasource.inputs.template_args = info

l1pipeline = pe.Workflow(name="level1")
l1pipeline.base_dir = os.path.abspath('bootstrapping/workingdir')

bootstrap_pipeline = pe.Workflow(name="bootstrap_wf")

bootstrap = pe.Node(interface=misc.BootstrapTimeSeries(), name="bootstrap")
id = range(150)
bootstrap.iterables = ('id',id)

bootstrap_pipeline.connect([
                  (modelspec_detrend,level1design_detrend,[('session_info','session_info')]),
                  (level1design_detrend,level1estimate_detrend,[('spm_mat_file','spm_mat_file')]),
                  (level1estimate_detrend, join_residuals, [('residual_images', 'in_files')]),
                  (join_residuals, img2float, [('merged_file', 'in_file')]),
                  (img2float, bootstrap, [('out_file', 'original_volume')]),
                  
                  (bootstrap, analysis_pipeline, [('bootstraped_volume', 'modelspec.functional_runs')]),
                  (level1estimate_detrend, analysis_pipeline, [('mask_image', 'level1design.mask_image')])
                  ])

l1pipeline.connect([(infosource, datasource, [('subject_id', 'subject_id')]),
                  (datasource, preproc_pipeline, [('func', 'realign.in_files')]),
                  (datasource, preproc_pipeline, [('struct', 'coregister.target')]),
                  
                  (preproc_pipeline, bootstrap_pipeline, [('realign.realignment_parameters','modelspecd.realignment_parameters'),
                                                          ('art.outlier_files','modelspecd.outlier_files'),
                                                          ('smooth.smoothed_files','modelspecd.functional_runs')])         
                  ])


TR = 3.

l1pipeline.inputs.bootstrap_wf.modelspecd.concatenate_runs        = True
l1pipeline.inputs.bootstrap_wf.modelspecd.concatenate_runs        = True
l1pipeline.inputs.bootstrap_wf.modelspecd.input_units             = 'secs'
l1pipeline.inputs.bootstrap_wf.modelspecd.output_units            = 'secs'
l1pipeline.inputs.bootstrap_wf.modelspecd.time_repetition         = TR
l1pipeline.inputs.bootstrap_wf.modelspecd.high_pass_filter_cutoff = 120
l1pipeline.inputs.bootstrap_wf.modelspecd.subject_info            = [Bunch(conditions=[],
                                                                                onsets=[],
                                                                                durations=[],
                                                                                amplitudes=None,
                                                                                tmod=None,
                                                                                pmod=None,
                                                                                regressor_names=None,
                                                                                regressors=None) for _ in range(4)]
l1pipeline.inputs.bootstrap_wf.level1designd.interscan_interval      = TR
l1pipeline.inputs.bootstrap_wf.level1designd.timing_units = l1pipeline.inputs.bootstrap_wf.modelspecd.output_units


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

l1pipeline.inputs.bootstrap_wf.bootstrap.blocks_info = Bunch(onsets = subjectinfo[0].onsets, duration = [10, 10])


l1pipeline.inputs.bootstrap_wf.analysis.modelspec.time_repetition         = TR
l1pipeline.inputs.bootstrap_wf.analysis.modelspec.subject_info            = subjectinfo
l1pipeline.inputs.bootstrap_wf.analysis.modelspec.input_units             = 'scans'
l1pipeline.inputs.bootstrap_wf.analysis.modelspec.output_units            = 'scans'

l1pipeline.inputs.bootstrap_wf.analysis.level1design.interscan_interval      = TR
l1pipeline.inputs.bootstrap_wf.analysis.level1design.timing_units = l1pipeline.inputs.bootstrap_wf.analysis.modelspec.output_units

cont1 = ('Task>Baseline','T', ['Task-Odd','Task-Even'],[0.5,0.5])
contrasts = [cont1]
l1pipeline.inputs.bootstrap_wf.analysis.contrastestimate.contrasts = contrasts

l1pipeline.inputs.bootstrap_wf.analysis.threshold.contrast_index = 1
l1pipeline.inputs.bootstrap_wf.analysis.threshold.use_fwe_correction = True

standard_analysis = analysis_pipeline.clone("standard_analysis")
standard_analysis.inputs.modelspec.high_pass_filter_cutoff = 120
standard_analysis.inputs.modelspec.input_units = 'secs'
standard_analysis.inputs.modelspec.output_units= 'secs'


subjectinfo_standard = []
for r in range(4):
    onsets = [range(15,240,60),range(45,240,60)]
    subjectinfo_standard.insert(r,
                  Bunch(conditions=names,
                        onsets=deepcopy(onsets),
                        durations=[[15] for s in names],
                        amplitudes=None,
                        tmod=None,
                        pmod=None,
                        regressor_names=None,
                        regressors=None))
    
standard_analysis.inputs.modelspec.subject_info = subjectinfo_standard
standard_analysis.inputs.modelspec.concatenate_runs        = True
standard_analysis.inputs.level1design.model_serial_correlations = "AR(1)"
standard_analysis.inputs.level1design.timing_units = 'secs'

l1pipeline.connect([(preproc_pipeline, standard_analysis, [('realign.realignment_parameters','modelspec.realignment_parameters'),
                                                          ('art.outlier_files','modelspec.outlier_files'),
                                                          ('smooth.smoothed_files','modelspec.functional_runs')])])

split_analysis = analysis_pipeline.clone("split_analysis")
l1pipeline.connect([(img2float, split_analysis, [('out_file', 'modelspec.functional_runs')]),
                    (level1estimate_detrend, split_analysis, [('mask_image', 'level1design.mask_image')])])

divide_maps = pe.Node(interface=fsl.ImageMaths(op_string = "-div"), name = "divide")
substract_maps = pe.Node(interface=fsl.ImageMaths(op_string = "-sub"), name = "substract")

l1pipeline.connect([(split_analysis, divide_maps, [('contrastestimate.spmT_images', 'in_file')]),
                    (standard_analysis, divide_maps, [('contrastestimate.spmT_images', 'in_file2')]),
                    (split_analysis, substract_maps, [('contrastestimate.spmT_images', 'in_file')]),
                    (standard_analysis, substract_maps, [('contrastestimate.spmT_images', 'in_file2')]),
                    ])


l2pipeline = pe.Workflow(name="level2")
l2pipeline.base_dir = os.path.abspath('bootstrapping/workingdir')

l2source = pe.Node(nio.DataGrabber(infields=["subject_id", "id"]),name="l2source")
l2source.inputs.template=os.path.abspath('bootstrapping/workingdir/level1/_subject_id_%s/_id_%d/threshold/thresholded_map.img')
l2source.inputs.id = id
l2source.iterables = [('subject_id',subject_list)]
frequency_map = pe.Node(misc.FrequencyMap(), name="frequency_map")

simple_threshold = pe.Node(misc.SimpleThreshold(), name="simple_threshold")
simple_threshold.iterables = [('threshold',[0.9, 0.95, 0.99])]

l2pipeline.connect([
                    (l2source,frequency_map, [('outfiles', 'binary_images')]),
                    (frequency_map, simple_threshold, [('frequency_map','volumes')])
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
    l1pipeline.write_graph()
#    l2pipeline.run()
