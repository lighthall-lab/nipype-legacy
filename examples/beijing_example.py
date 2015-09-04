from nipype.pipeline.engine import Workflow, Node
from nipype.interfaces.io import SelectFiles, DataSink
from nipype.interfaces.fsl import MCFLIRT, BET

templates={"T1": "sub-01/ses-{ses}/anatomy/sub-01_ses-{ses}_T1w.nii.gz",
           "epi": "sub-01/ses-{ses}/functional/sub-01_ses-{ses}_task-overtwordrepetition_bold.nii.gz"}
datagraber = Node(SelectFiles(templates), name="datagrabber")
datagraber.inputs.base_directory = "/Users/filo/chrisgor@stanford.edu/bids_examples/ds114"
datagraber.iterables = [("ses", ["test", "retest"])]

motion_correction = Node(MCFLIRT(), name="motion_correction")
motion_correction.inputs.save_plots = True
motion_correction.inputs.mean_vol = True

skullstrip = Node(BET(), name="skullstrip")
skullstrip.inputs.functional = True
skullstrip.inputs.mask = True

datasink = Node(DataSink(), name="datasink")
datasink.inputs.base_directory = "/Users/filo/results"

workflow = Workflow(name="preprocessing")
workflow.base_dir = "/tmp/working_directory"

workflow.connect(datagraber, "epi", motion_correction, "in_file")
workflow.connect(motion_correction, "mean_img", skullstrip, "in_file")
workflow.connect(skullstrip, "mask_file", datasink, "mask_file")

workflow.write_graph()

workflow.run()
