"""
Module: acoustic_survey.py
Authors: Clea Parcerisas
Institution: VLIZ (Vlaams Institute voor de Zee)
"""

import os
import glob
import pathlib
import zipfile
import datetime
import operator
import acoustics
import numpy as np
import numba as nb
import pandas as pd
import soundfile as sf
import scipy.signal as sig
import matplotlib.pyplot as plt
import scipy.integrate as integrate

from pathlib import Path

pd.plotting.register_matplotlib_converters()
plt.style.use('ggplot')

from pypam.acoustic_file import HydroFile, MEMSFile, MEMS3axFile, Sxx2spd



class ASA:
    def __init__(self, hydrophone, folder_path, zipped=False, include_dirs=False, p_ref=1.0, binsize=None, nfft=1.0, period=None, band=None, utc=True):
        """ 
        Init a AcousticSurveyAnalysis (ASA)

        Parameters
        ----------
        hydrophone : Hydrophone class from pyhhydrophone
        folder_path : string or Path
            Where all the sound files are 
        zipped : boolean
            Set to True if the directory is zipped
        include_dirs : boolean
            Set to True if the folder contains other folders with sound files
        p_ref : float
            Reference pressure in uPa
        binsize : float
            Time window considered, in seconds. If set to None, only one value is returned
        nfft : int
            Samples of the fft bin used for the spectral analysis
        period : tuple or list
            Tuple or list with two elements: start and stop. Has to be a string in the format YYYY-MM-DD HH:MM:SS
        band : tuple or list
            Tuple or list with two elements: low-cut and high-cut of the band to analyze
        """
        self.hydrophone = hydrophone
        self.acu_files = self.AcousticFolder(folder_path=folder_path, zipped=zipped, include_dirs=include_dirs)
        self.p_ref = p_ref
        self.binsize = binsize
        self.nfft = nfft
        self.band = band

        if period is not None:
            if not isinstance(period[0], datetime.datetime):
                start = datetime.datetime.strptime(period[0], '%Y-%m-%d %H:%M:%S')
                end = datetime.datetime.strptime(period[1], '%Y-%m-%d %H:%M:%S')
                self.period = [start, end]
            else:
                self.period = period
        else:
            self.period = None
        
        self.utc = utc
        


    def evolution_multiple(self, method_list, **kwargs):
        """
        Compute the method in each file and output the evolution
        Returns a DataFrame with datetime as index and one row for each bin of each file

        Parameters
        ----------
        method_list : string
            Method name present in HydroFile
        **kwargs : 
            Any accepted parameter for the method_name
        """
        df = pd.DataFrame()
        f = operator.methodcaller('_apply_multiple', method_list=method_list, binsize=self.binsize, **kwargs)
        for file_list in self.acu_files:
            wav_file = file_list[0]
            print(wav_file)
            sound_file = HydroFile(sfile=wav_file, hydrophone=self.hydrophone, p_ref=self.p_ref, band=self.band, utc=self.utc)
            if sound_file.is_in_period(self.period):
                try:
                    df_output = f(sound_file)
                    df = df.append(df_output)
                except:
                    print('%s had some problems and was not added to the evolution' % (wav_file))
        
        return df
    

    def evolution(self, method_name, **kwargs):
        """
        Evolution of only one param name 
        """
        return self.evolution_multiple(method_list=[method_name], **kwargs)



    def timestamps_df(self):
        """
        Return a pandas dataframe with the timestamps of each bin.
        Parameters
        ----------
        binsize : float, in sec
            Time window considered. If set to None, only one value is returned
        dB : None
            Does not apply. It is ignored
        nfft : None
            Does not apply. It is ignored
        """
        df = pd.DataFrame()
        f = operator.methodcaller('timestamps_df', binsize=self.binsize)
        for file_list in self.acu_files:
            wav_file = file_list[0]
            print(wav_file)
            sound_file = HydroFile(sfile=wav_file, hydrophone=self.hydrophone, p_ref=self.p_ref, band=self.band, utc=self.utc)
            if sound_file.is_in_period(self.period):
                try:
                    df_output = f(sound_file)
                    df = df.append(df_output, ignore_index=True)
                except:
                    print('%s had some problems and was not added to the evolution' % (wav_file))
        
        return df
    

    def start_end_timestamp(self):
        """
        Return the start and the end timestamps
        """
        file_list = self.acu_files[0]
        wav_file = file_list[0]
        print(wav_file)
        sound_file = HydroFile(sfile=wav_file, hydrophone=self.hydrophone, p_ref=self.p_ref, band=self.band, utc=self.utc)
        start_datetime = sound_file.date

        file_list = self.acu_files[-1]
        wav_file = file_list[0]
        print(wav_file)
        sound_file = HydroFile(sfile=wav_file, hydrophone=self.hydrophone, p_ref=self.p_ref, band=self.band, utc=self.utc)
        end_datetime = sound_file.date + datetime.timedelta(seconds=sound_file.total_time())
        
        return start_datetime, end_datetime


    def apply_to_all(self, method_name, **kwargs):
        """
        Apply the method to all the files
        
        Parameters
        ----------
        method_name : string
            Method name present in HydroFile
        **kwargs : 
            Any accepted parameter for the method_name

        """
        f = operator.methodcaller(method_name, **kwargs)
        for file_list in self.acu_files:
            wav_file = file_list[0]
            print(wav_file)
            sound_file = HydroFile(sfile=wav_file, hydrophone=self.hydrophone, p_ref=self.p_ref, band=self.band, utc=self.utc)
            if sound_file.is_in_period(self.period):
                try:
                    f(sound_file)
                except:
                    print('%s had some problems and was not added to the analysis' % (wav_file))
    

    def duration(self):
        """
        Return the duration in seconds of all the survey
        """
        total_time = 0
        for file_list in self.acu_files:
            wav_file = file_list[0]
            print(wav_file)
            sound_file = HydroFile(sfile=wav_file, hydrophone=self.hydrophone, p_ref=self.p_ref, band=self.band, utc=self.utc)
            if sound_file.is_in_period(self.period):
                try:
                    total_time += sound_file.total_time()
                except:
                    print('%s had some problems and was not added to the analysis' % (wav_file))  

        return total_time      


    def mean_rms(self, **kwargs):
        """
        Return the mean root mean squared value of the survey
        Accepts any other input than the correspondant method in the acoustic file.
        Returns the rms value of the whole survey

        Parameters
        ----------
        **kwargs : 
            Any accepted arguments for the rms function of the AcuFile
        """
        rms_evolution = self.evolution('rms', **kwargs)
            
        return rms_evolution['rms'].mean()


    def spd(self, dB=True, h=0.1, percentiles=[]):
        """
        Return the empirical power density. 

        Parameters
        ----------
        dB : boolean
            If set to True the result will be given in dB. Otherwise in uPa^2
        h : float
            Histogram bin (in the correspondent units, uPa or dB)
        percentiles : list
            All the percentiles that have to be returned. If set to None, no percentiles is returned

        Returns
        ------- 
        fbands : list
            List of all the frequencies
        bin_edges : list
            List of the psd values of the distribution
        spd : DataFrame
            DataFrame with 'frequency' as index and a colum for each psd bin and for each percentile
        p : numpy matrix
            Matrix with all the probabilities
        """
        psd_evolution = self.evolution('psd', dB=dB, percentiles=percentiles)
        fbands = psd_evolution['band_density'].columns
        Pxx = psd_evolution['band_density'][fbands].to_numpy(dtype=np.float).T
        # Calculate the bins of the psd values and compute spd using numba
        bin_edges = np.arange(start=Pxx.min(), stop=Pxx.max(), step=h)
        spd, p = Sxx2spd(Sxx=Pxx, h=h, percentiles=np.array(percentiles)/100.0, bin_edges=bin_edges)
        
        return fbands, bin_edges, spd, percentiles, p


    def cut_and_place_files_period(self, period, folder_name, extensions=[]):
        """
        Cut the files in the specified periods and store them in the right folder 

        Parameters
        ----------
        period: Tuple or list
            Tuple or list with (start, stop)
        extensions: list of strings
            the extensions that want to be moved (csv will be splitted, log will just be moved)
        """
        start_date = datetime.datetime.strptime(period[0], '%d/%m/%Y %H:%M:%S')
        end_date = datetime.datetime.strptime(period[1], '%d/%m/%Y %H:%M:%S')
        print(start_date, end_date)
        folder_path = os.path.join(self.acu_files.folder_path, folder_name)
        self.acu_files.extensions = extensions
        for file_list in self.acu_files:
            wav_file = file_list[0]
            sound_file = HydroFile(sfile=wav_file, hydrophone=self.hydrophone, p_ref=self.p_ref, band=self.band, utc=self.utc)
            if sound_file.contains_date(start_date):
                print('start!', wav_file)
                # Split the sound file in two files
                first, second = sound_file.split(start_date)
                move_file(second, folder_path)   
                # Split the metadata files
                for i, metadata_file in enumerate(file_list[1:]):
                    if extensions[i] != '.log.xml':
                        df = pd.read_csv(metadata_file)
                        df['datetime'] = pd.to_datetime(df['unix time']*1e9) + datetime.timedelta(hours=2)
                        df_first = df[df['datetime'] < start_date]
                        df_second = df[df['datetime'] >= start_date]
                        df_first.to_csv(metadata_file)
                        new_metadata_path = pathlib.Path(second._str.replace('.wav', extensions[i]))
                        df_second.to_csv(new_metadata_path)
                        # Move the file 
                        move_file(new_metadata_path, folder_path)                         
            elif sound_file.contains_date(end_date):  
                print('end!', wav_file)          
                # Split the sound file in two files
                first, second = sound_file.split(end_date)
                move_file(first, folder_path)   
                # Split the metadata files
                for i, metadata_file in enumerate(file_list[1:]):
                    if extensions[i] != '.log.xml':
                        df = pd.read_csv(metadata_file)
                        df['datetime'] = pd.to_datetime(df['unix time']*1e9) + datetime.timedelta(hours=2)
                        df_first = df[df['datetime'] < start_date]
                        df_second = df[df['datetime'] >= start_date]
                        df_first.to_csv(metadata_file)
                        new_metadata_path = pathlib.Path(second._str.replace('.wav', extensions[i]))
                        df_second.to_csv(new_metadata_path)
                    # Move the file (also if log)
                    move_file(metadata_file, folder_path)    
                
            else: 
                if sound_file.is_in_period([start_date, end_date]):
                    print('moving', wav_file)
                    sound_file.file.close()
                    move_file(wav_file, folder_path)
                    for metadata_file in file_list[1:]:
                        move_file(metadata_file, folder_path)       
                else:
                    pass         

        return 0 


    def plot_all_files(self, method_name, **kwargs):
        """
        Apply the plot method to all the files

        Parameters
        ----------
        method_name : string 
            Plot method present in HydroFile
        **kwargs : Any accepted in the method_name
        """
        self.apply_to_all(binsize=self.binsize, nfft=self.nfft, **kwargs)


    def plot_rms_evolution(self, dB=True, save_path=None):
        """
        Plot the rms evolution

        Parameters
        ----------
        dB : boolean 
            If set to True, output in dB 
        save_path : string or Path 
            Where to save the output graph. If None, it is not saved
        """
        rms_evolution = self.evolution('rms', dB=dB)
        plt.figure()
        plt.plot(rms_evolution['rms'])
        plt.xlabel('Time')
        if dB: 
            units = 'dB re 1V %s uPa' % (self.p_ref)
        else:
            units = 'uPa'
        plt.title('Evolution of the broadband rms value')       # Careful when filter applied!
        plt.ylabel('rms [%s]' % (units))
        plt.tight_layout()
        if save_path is not None: 
            plt.savefig(save_path)
        else:
            plt.show()
        plt.close()


    def plot_rms_daily_patterns(self, dB=True, save_path=None):
        """
        Plot the daily rms patterns

        Parameters
        ----------
        dB : boolean 
            If set to True, output in dB 
        save_path : string or Path 
            Where to save the output graph. If None, it is not saved
        """
        rms_evolution = self.evolution('rms', dB=dB)
        rms_evolution['date'] = rms_evolution.index.date.unique()
        rms_evolution['hour'] = rms_evolution.index.time
        dates = rms_evolution['dates'].unique()
        hours = rms_evolution['hours'].unique()
        daily_patterns = pd.DataFrame()
        for date in dates: 
            for hour in hours:
                rms = rms_evolution[(rms_evolution['date'] == date) & (rms_evolution['hour'] == hour)]['rms']
                daily_patterns.loc[date, hour] = rms
        
        # Plot the patterns
        plt.figure()
        im = plt.pcolormesh(daily_patterns.values)
        plt.title('Daily patterns') 
        plt.xlabel('Hours of the day')
        plt.ylabel('Days')

        if dB: 
            units = 'dB re 1V %s uPa' % (self.p_ref)
        else:
            units = 'uPa'
        cbar = plt.colorbar(im)
        cbar.set_label('rms [%s]' % (units), rotation=270)
        plt.tight_layout()
        if save_path is not None: 
            plt.savefig(save_path)
        else:
            plt.show()
        plt.close()   


    def plot_mean_power_spectrum(self, dB=True, save_path=None, log=True, **kwargs):
        """
        Plot the resulting mean power spectrum

        Parameters
        ----------
        dB : boolean 
            If set to True, output in dB 
        log : boolean 
            If set to True, y axis in logarithmic scale
        save_path : string or Path 
            Where to save the output graph. If None, it is not saved
        **kwargs : Any accepted for the power_spectrum method
        """
        power = self.evolution(method_name='power_spectrum', dB=dB, **kwargs)
        if dB: 
            units = 'dB re 1V %s uPa^2' % (self.p_ref)
        else:
            units = 'uPa^2' 
        
        return self._plot_spectrum_mean(df=power, units=units, col_name='spectrum', output_name='SPLrms', dB=dB, save_path=save_path, log=log)


    def plot_mean_psd(self, dB=True, save_path=None, log=True, **kwargs):
        """
        Plot the resulting mean psd

        Parameters
        ----------
        dB : boolean 
            If set to True, output in dB 
        log : boolean 
            If set to True, y axis in logarithmic scale
        save_path : string or Path 
            Where to save the output graph. If None, it is not saved
        **kwargs : Any accepted for the psd method
        """
        psd = self.evolution(method_name='psd', dB=dB, **kwargs)
        if dB: 
            units = 'dB re 1V %s uPa^2' % (self.p_ref)
        else:
            units = 'uPa^2' 
        
        return self._plot_spectrum_mean(df=psd, units=units, col_name='density', output_name='PSD', dB=dB, save_path=save_path, log=log)


    def _plot_spectrum_mean(self, df, units, col_name, output_name, dB=True, save_path=None, log=True):
        """
        Plot the mean spectrum

        Parameters
        ----------
        df : DataFrame
            Output of evolution
        units : string 
            Units of the spectrum
        col_name : string 
            Column name of the value to plot. Can be 'density' or 'spectrum'
        output_name : string
            Name of the label. 'PSD' or 'SPLrms'
        dB : boolean 
            If set to True, output in dB 
        log : boolean 
            If set to True, y axis in logarithmic scale
        save_path : string or Path 
            Where to save the output graph. If None, it is not saved
        """
        fbands = df['band_'+col_name].columns
        fig = plt.figure()
        mean_spec = df['band_'+col_name][fbands].mean(axis=0)
        plt.plot(fbands, mean_spec)
        plt.title(col_name.capitalize())
        plt.xlabel('Frequency [Hz')
        plt.ylabel('%s [%s]' % (output_name, units))

        # Plot the percentile lines
        percentiles = df['percentiles'].mean(axis=0).values
        plt.hlines(y=percentiles, xmin=fbands.min(), xmax=fbands.max(), label=df['percentiles'].columns)

        plt.tight_layout()
        if save_path is not None: 
            plt.savefig(save_path)
        else:
            plt.show()
        plt.close()   

        return fbands, mean_spec, percentiles


    def plot_power_ltsa(self, dB=True, save_path=None, **kwargs):
        """
        Plot the evolution of the power frequency distribution

        Parameters
        ----------
        dB : boolean 
            If set to True, output in dB 
        save_path : string or Path 
            Where to save the output graph. If None, it is not saved
        **kwargs : Any accepted for the power spectrum method
        """
        power_evolution = self.evolution('power_spectrum', dB=dB, **kwargs)
        if dB: 
            units = 'dB re 1V %s uPa^2' % (self.p_ref)
        else:
            units = 'uPa^2' 
        self._plot_ltsa(df=power_evolution, col_name='spectrum', output_name='SPLrms', units=units, dB=dB, save_path=save_path)

        return power_evolution
    

    def plot_psd_ltsa(self, dB=True, save_path=None, **kwargs):
        """
        Plot the evolution of the psd 

        Parameters
        ----------
        dB : boolean 
            If set to True, output in dB 
        save_path : string or Path 
            Where to save the output graph. If None, it is not saved
        **kwargs : Any accepted for the psd method
        """
        psd_evolution = self.evolution('psd', dB=dB, **kwargs)
        if dB: 
            units = 'dB re 1V %s uPa^2/Hz' % (self.p_ref)
        else:
            units = 'uPa^2/Hz' 
        self._plot_ltsa(df=psd_evolution, col_name='density', output_name='PSD', units=units, dB=dB, save_path=save_path)

        return psd_evolution
    

    def _plot_ltsa(self, df, col_name, output_name, units, dB=True, save_path=None):
        """
        Plot the evolution of the df containing percentiles and band values

        Parameters
        ----------
        df : DataFrame
            Output of evolution
        units : string 
            Units of the spectrum
        col_name : string 
            Column name of the value to plot. Can be 'density' or 'spectrum'
        output_name : string
            Name of the label. 'PSD' or 'SPLrms'
        dB : boolean 
            If set to True, output in dB 
        save_path : string or Path 
            Where to save the output graph. If None, it is not saved
        """
        # Plot the evolution  
        # Extra axes for the colorbar and delete the unused one
        fig, ax = plt.subplots(2, 2, sharex='col', gridspec_kw={'width_ratios' : (15,1)})
        fbands = df['band_'+col_name].columns
        im = ax[0,0].pcolormesh(df.index, fbands, df['band_'+col_name][fbands].T.to_numpy(dtype=np.float))
        ax[0,0].set_title('%s evolution' % (col_name.capitalize()))
        ax[0,0].set_xlabel('Time')
        ax[0,0].set_ylabel('Frequency [Hz]')
        cbar = fig.colorbar(im, cax=ax[0,1])
        cbar.set_label('%s [%s]' % (output_name, units), rotation=90)
        # Remove the unused axes
        ax[1,1].remove()

        ax[1,0].plot(df['percentiles'])
        ax[1,0].set_title('Percentiles evolution')
        ax[1,0].set_xlabel('Time')
        ax[1,0].set_ylabel('%s [%s]' % (output_name, units))
        ax[1,0].legend(df['percentiles'].columns.values)

        plt.tight_layout()
        if save_path is not None: 
            plt.savefig(save_path)
        else:
            plt.show()
        plt.close()   

    
    def plot_spd(self, dB=True, log=True, save_path=None, **kwargs):
        """
        Plot the the SPD graph

        Parameters
        ----------
        dB : boolean 
            If set to True, output in dB 
        log : boolean 
            If set to True, y axis in logarithmic scale
        save_path : string or Path 
            Where to save the output graph. If None, it is not saved
        **kwargs : Any accepted for the spd method
        """
        fbands, bin_edges, spd, percentiles, p = self.spd(dB=dB, **kwargs)
        if dB: 
            units = 'dB re 1V %s uPa^2/Hz' % (self.p_ref)
        else:
            units = 'uPa^2/Hz'

        # Plot the EPD
        fig = plt.figure()
        im = plt.pcolormesh(fbands, bin_edges, spd.T, cmap='BuPu')
        if log: 
            plt.xscale('log')
        plt.title('Spectral probability density')
        plt.xlabel('Frequency [Hz]')
        plt.ylabel('PSD [%s]' % (units))
        cbar = fig.colorbar(im)
        cbar.set_label('Empirical Probability Density', rotation=90)
        
        # Plot the lines of the percentiles
        if len(percentiles) != 0:
            plt.plot(fbands, p, label=percentiles)

        plt.tight_layout()
        if save_path is not None: 
            plt.savefig(save_path)
        else:
            plt.show()
        plt.close()  

        return fbands, bin_edges, spd, percentiles, p


    class AcousticFolder:
        """
        Class to help through the iterations of the acoustic folder.
        """
        def __init__(self, folder_path, zipped=False, include_dirs=False, extensions=[]):
            """
            Store the information about the folder.
            It will create an iterator that returns all the pairs of extensions having the same name than the wav file 

            Parameters
            ----------
            folder_path : string
                Path to the folder containing the acoustic files
            zipped : boolean
                Set to True if the subfolders are zipped
            include_dirs : boolean 
                Set to True if the subfolders are included in the study
            extensions : list
                List of strings with all the extensions that will be returned (.wav is automatic)
                i.e. extensions=['.xml', '.bcl'] will return [wav, xml and bcl] files
            """
            self.folder_path = Path(folder_path)
            self.zipped = zipped
            self.recursive = include_dirs
            self.extensions = extensions


        def __getitem__(self, n):
            """
            Get n wav file
            """
            self.__iter__()
            self.n = n
            return self.__next__()


        def __iter__(self):
            """
            Iteration
            """
            self.n = 0       
            if not self.zipped:
                if self.recursive:
                    self.files_list = sorted(self.folder_path.glob('**/*.wav'))
                else:
                   self.files_list = sorted(self.folder_path.glob('*.wav'))
            else:
                if self.recursive:
                    self.folder_list = self.folder.iterdir()
                    self.zipped_subfolder = AcousticFolder(self.folder_list[self.n], extensions=self.extensions, zipped=self.zipped, include_dirs=self.recursive)
                else:
                    zipped_folder = zipfile.ZipFile(self.folder_path, 'r', allowZip64=True)
                    self.files_list = zipped_folder.namelist()
            return self


        def __next__(self):
            """
            Next wav file
            """
            if self.n < len(self.files_list):
                files_list = []
                if self.zipped:
                    if self.recursive:
                        try:
                            files_list = self.zipped_subfolder.__next__()
                        except StopIteration:
                            self.n += 1
                            self.zipped_subfolder = AcousticFolder(self.folder_list[self.n], extensions=self.extensions, zipped=self.zipped, include_dirs=self.recursive)
                    else:
                        file_name = self.files_list[self.n]
                        extension = file_name.split(".")[-1]
                        if extension == 'wav':
                            wav_file = self.folder.open(file_name)
                            files_list.append(wav_file)
                            for extension in self.extensions:
                                files_list.append(self.folder.open(file_name.replace('.wav', extension)))
                        self.n += 1
                        return files_list
                else:
                    wav_path = self.files_list[self.n]
                    files_list.append(wav_path)
                    for extension in self.extensions:
                        files_list.append(Path(str(wav_path).replace('.wav', extension)))
                
                    self.n += 1
                    return files_list
            else:
                raise StopIteration
        

        def __len__(self):
            if not self.zipped:
                if self.recursive:
                    n_files = len(list(self.folder_path.glob('**/*.wav')))
                else:
                    n_files = len(list(self.folder_path.glob('*.wav')))
            else:
                if self.recursive:
                    n_files = len(list(self.folder.iterdir()))
                else:
                    zipped_folder = zipfile.ZipFile(self.folder_path, 'r', allowZip64=True)
                    n_files = len(zipped_folder.namelist())
            return n_files            



def move_file(file_path, new_folder_path):
    """
    Move the file to the new folder

    Parameters
    ----------
    file_path : string or Path 
        Original file path 
    new_folder_path : string or Path 
        New folder destination (without the file name)
    """
    if not isinstance(file_path, pathlib.Path):
        file_path = pathlib.Path(file_path)
    if not isinstance(new_folder_path, pathlib.Path):
        new_folder_path = pathlib.Path(new_folder_path)
    if not os.path.exists(new_folder_path):
        os.makedirs(new_folder_path)
    new_path = new_folder_path.joinpath(file_path.name)
    os.rename(file_path, new_path)

