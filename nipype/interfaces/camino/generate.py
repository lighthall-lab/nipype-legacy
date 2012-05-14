from nipype.interfaces.base import StdOutCommandLineInputSpec, File, traits,\
    TraitedSpec, StdOutCommandLine, isdefined
import os


class DataSynthInputSpec(StdOutCommandLineInputSpec):
    traj_file = traits.Either(traits.Bool, File(),
                              hash_files=False,
                              desc="Output traj file.",
                              argstr="-trajFile %s")


class DataSynthOutputSpec(TraitedSpec):
    traj_file = File(exists=True)
    synthetic_measurements = File(exists=True)


class DataSynth(StdOutCommandLine):
    """
    Example
    -------

    >>> import nipype.interfaces.camino as cmon
    >>> ds = cmon.DataSynth()
    >>> ds.cmdline
    'datasynth > SyntheticMeasurements.Bfloat'
    >>> ds.inputs.out_file = 'SyntheticMeasurements1000.Bfloat'
    >>> ds.cmdline
    'datasynth > SyntheticMeasurements1000.Bfloat'
    >>> ds2 = cmon.DataSynth()
    >>> ds2.inputs.traj_file = True
    >>> ds2.cmdline
    'datasynth -trajFile MC.traj '
    >>> ds2.inputs.traj_file = 'MC1000.traj'
    >>> ds2.cmdline
    'datasynth -trajFile MC1000.traj '
    """
    input_spec = DataSynthInputSpec
    output_spec = DataSynthOutputSpec
    _cmd = 'datasynth'

    def _gen_outfilename(self):
        return "SyntheticMeasurements.Bfloat"

    def _gen_filename(self, name):
        if name is 'traj_file':
            return 'MC.traj'
        else:
            return super(DataSynth, self)._gen_filename(name)

    def _format_arg(self, name, spec, value):
        if name == 'traj_file':
            if isinstance(value, bool):
                if value == True:
                    value = self._gen_filename(name)
                else:
                    return ""
        elif name == 'out_file':
            if isdefined(self.inputs.traj_file) and self.inputs.traj_file:
                return ""
            else:
                return super(DataSynth, self)._format_arg(name, spec, value)
        return super(DataSynth, self)._format_arg(name, spec, value)

    def _list_outputs(self):
        outputs = self.output_spec().get()
        if isdefined(self.inputs.traj_file) and self.inputs.traj_file:
            if isinstance(self.inputs.traj_file, bool):
                outputs['traj_file'] = os.path.abspath(self._gen_filename("traj_file"))
            else:
                outputs['traj_file'] = os.path.abspath(self.inputs.traj_file)
        else:
            outputs['synthetic_measurements'] = os.path.abspath(self._gen_filename("out_file"))

        return self._outputs_from_inputs(outputs)
