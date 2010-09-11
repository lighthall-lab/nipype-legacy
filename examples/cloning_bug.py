import nipype.interfaces.io as nio           # Data i/o
import nipype.interfaces.fsl as fsl          # fsl
import nipype.interfaces.utility as util     # utility
import nipype.pipeline.engine as pe          # pypeline engine
import os                                    # system functions


datasource1 = pe.Node(interface=nio.DataGrabber(), name='datasource1')
datasource1.inputs.template = os.path.abspath("data/s1/struct.nii")

datasource2 = pe.Node(interface=nio.DataGrabber(), name='datasource2')
datasource2.inputs.template = os.path.abspath("data/s3/struct.nii")

test_pipeline = pe.Workflow(name="test_pipeline1")

test_node = pe.Node(interface=fsl.ImageMaths(), name="test_node1")
test_node.inputs.op_string = "-add 1"

test_node2 = pe.Node(interface=fsl.ImageMaths(), name="test_node2")
test_node2.inputs.op_string = "-add 1"

test_pipeline.connect([(test_node,test_node2, [('out_file', 'in_file')])
                       ])

l1 = pe.Workflow(name="l1")
l1.base_dir = "cloning_bug"

l1.connect([(datasource1, test_pipeline, [('outfiles', 'test_node1.in_file')])])

test_node3 = pe.Node(interface=fsl.ImageMaths(), name="test_node3")
test_node3.iterables = ('op_string', ["-add 1", "-add 2","-add 3"])

test_pipeline2 = test_pipeline.clone("test_pipeline2")

l1.connect([(datasource1, test_node3, [('outfiles', 'in_file')]),
             (test_node3, test_pipeline2, [('out_file', 'test_node1.in_file')])])

l1.run()