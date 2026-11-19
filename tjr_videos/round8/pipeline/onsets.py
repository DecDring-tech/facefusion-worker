import numpy as np, librosa
def peaks(path, sr=22050, hop=64):
    y,_=librosa.load(path,sr=sr)
    o=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,aggregate=np.median); ol=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop,fmax=200,n_mels=32)
    o=o/o.max()+ol/ol.max(); t=librosa.frames_to_time(np.arange(len(o)),sr=sr,hop_length=hop)
    pk=librosa.util.peak_pick(o,pre_max=20,post_max=20,pre_avg=60,post_avg=60,delta=0.06,wait=15)
    return t[pk], o[pk], o, t
