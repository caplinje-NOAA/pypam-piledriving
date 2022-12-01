import unittest

from pypam.acoustic_file import AcuFile
import pyhydrophone as pyhy

# Another hydrophone
st = pyhy.SoundTrap('SoundTrap', 'ST600HF', '6716')


# Hydrophone Setup
# If Vpp is 2.0 then it means the wav is -1 to 1 directly related to V
model = 'ST300HF'
name = 'SoundTrap'
serial_number = 67416073
soundtrap = pyhy.soundtrap.SoundTrap(name=name, model=model, serial_number=serial_number)


class TestAcuFile(unittest.TestCase):
    def setUp(self) -> None:
        self.acu_file = AcuFile('test_data/67416073.210610033655.wav', soundtrap, 1)

    def test_plots(self):
        self.acu_file.plot_power_spectrum()

    def test_millidecade_bands(self):
        nfft = 8000
        self.acu_file.hybrid_millidecade_bands(nfft, fft_overlap=0.5, binsize=None, bin_overlap=0, db=True,
                                               method='spectrum', band=None)
        self.acu_file.hybrid_millidecade_bands(nfft, fft_overlap=0.5, binsize=None, bin_overlap=0, db=True,
                                               method='density', band=None)