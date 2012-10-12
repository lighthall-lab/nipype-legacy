from nipype.interfaces.base import TraitedSpec, InputMultiPath, File, traits,\
    BaseInterface
import numpy as np
import os

class DCMStackInputSpec(TraitedSpec):
    dicom_files = InputMultiPath(File(exists=True), mandatory=True)
    out_filename = File("sequence.nii", hash_files=False, usedefault=True)
    
class DCMStackOutputSpec(TraitedSpec):
    nifti_file = File(exists=True)
    
class DCMStack(BaseInterface):
    input_spec = DCMStackInputSpec
    output_spec = DCMStackOutputSpec

    def _run_interface(self, runtime):
        import dcmstack, dicom
        my_stack = dcmstack.DicomStack()
        for src_path in self.inputs.dicom_files:
            src_dcm = dicom.read_file(src_path)
            my_stack.add_dcm(src_dcm)
        nii_wrp = my_stack.to_nifti_wrapper()
        nii_wrp.to_filename(os.path.abspath(self.inputs.out_filename))
        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()
        outputs["nifti_file"] = os.path.abspath(self.inputs.out_filename)
        return outputs
