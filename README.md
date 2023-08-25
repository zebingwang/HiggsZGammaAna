# HiggsZGammaAna
This is the full analysis chain of Run3 Higgs to ZGamma analysis. It is a combination of HiggsDNA, machine learning, spurial test and final fit. 

```
git clone https://github.com/Vvvvvvvictor/HiggsZGammaAna.git --recursive
```
## HiggsDNA for tagging
**1. Setup environment**

The conda env would occupy a large quota. Make sure that you have a few GB left in your path(exp. : `/eos/user`). This step would take a few hours, please keep patient.
```
cd HiggsZGammaAna/HiggsDNA/
conda env create -f environment.yml -p <some_path_where_you_have_more_disk_space>/.conda/envs/
```
Then, activate the conda environment

```
conda activate higgs-zg-ana
```

You may also want to increase your disk quota at [this link](https://resources.web.cern.ch/resources/Manage/EOS/Default.aspx), otherwise you may run out of space while installing your `conda` environment.

One additional package, `correctionlib`, must be installed via `pip`, rather than `conda`. Run
```
source setup.sh
```
to install this script.

**2. Add HiggsDNA package**

Install it by:
```
pip install -e .
```
If you notice issues with the `conda pack` command for creating the tarball, try updating and cleaning your environment with (after running `conda activate higgs-dna`):
```
conda env update --file environment.yml --prune
```

**3. Some useful note**

If you have some question of useage or code structure, please look at [HiggsDNA contents](https://sam-may.github.io/higgs_dna_tutorial.github.io/).

The name list of dataset can find in DAS system [(example)](https://cmsweb.cern.ch/das/request?instance=prod/global&input=file+dataset%3D%2FVBFHToZG_M-125_TuneCP5_13TeV-powheg-pythia8%2FRunIISummer19UL17NanoAODv2-106X_mc2017_realistic_v8-v1%2FNANOAODSIM). Then you can put them in `metadata/samples/zgamma_tutorial.json`.

If you are comfused with the cross-section of a MC dataset, please get it through [this link](https://xsdb-temp.app.cern.ch/?columns=38289920&currentPage=0&ordDirection=1&ordFieldName=process_name&pageSize=50). 

If you want to find the path of a dataset, please get it through [this link](https://cms-pdmv.cern.ch/mcm/requests?page=0&mcdb_id=102X_dataRun2_v11&shown=127).

If you want to get the golden json, these files, `/eos/user/c/cmsdqm/www/CAF/certification/Collisions*/Cert_Collisions*_*_*_Golden.json`, are recommended. Please put them in `metadata/golden_json/` and also change the golden json choice in the tagger you use.

You can find the name of variables in NanoAOD in [this link](https://cms-nanoaod-integration.web.cern.ch/autoDoc/NanoAODv11/2022postEE/doc_Muon_Run2022G-PromptNanoAODv11_v1-v2.html)

## Machine learning for categorization

### Setup environment
**1. Enter analysis environment**

Put this environment in HiggsDNA environment to reduce the space occupied by this program.
```
cd HiggsZGammaAna/hzgml
conda activate higgs-zg-ana
```
**2. Install packages**

Install the packages for machine learning(BDT and DNN).
```
pip install -r requirement.txt
```

### Scripts to run the tasks

#### Prepare the training inputs (skimmed ntuples)

The core script is `skim_ntuples.py`. The script will apply the given skimming cuts to input samples and produce corresponding skimmed ntuples. You can run it locally for any specified input files. In H->mumu, it is more convenient and time-efficient to use `submit_skim_ntuples.py` which will find all of the input files specified in `data/inputs_config.json` and run the core script by submitting the condor jobs.

- The script is hard-coded currently, meaning one needs to directly modify the core script to change the variable calculation and the skimming cuts.
- The output files (skimmed ntuples) will be saved to the folder named `skimmed_ntuples` by default.
- `submit_skim_ntuples.py` will only submit the jobs for those files that don't exist in the output folder.
- `run_skim_ntuples.sh` will run all skim jobs locally

```
sh scripts/run_skim_ntuples.sh
```
or
```
python scripts/skim_ntuples.py [-i input_file_path] [-o output_file_path]
```

#### Start XGBoost analysis!

The whole ML task consists of training, applying the weights, optimizing the BDT boundaries for categorization, and calculating the number counting significances. The wrapper script `run_all.sh` will run everything. Please have a look!

**1. Make some directories**
```
mkdir -p models outputs plots
```

**2. Training a model**

The training script `train_bdt.py` will train the model in four-fold, and transform the output scores such that the unweighted signal distribution is flat. The detailed settings, including the preselections, training variables, hyperparameters, etc, are specified in the config file `data/training_config.json`.

```
python scripts/train_bdt.py [-r TRAINED_MODEL] [-f FOLD] [--save]

Usage:
  -r, --region        The model to be trained. Choices: 'zero_jet', 'one_jet', 'two_jet' or 'VBF'.
  -f, --fold          Which fold to run. Default is -1 (run all folds)
  --save              To save the model into HDF5 files, and the pickle files
```

**3. Applying the weights**

Applying the trained model (as well as the score transformation) to the skimmed ntuples to get BDT scores for each event can be done by doing:
```
python scripts/apply_bdt.py [-r REGION]
```
The script will take the settings specified in the training config file `data/training_config.json` and the applying config file `data/apply_config.json`.

**4. Optimizing the BDT boundaries**

`categorization_1D.py` will take the Higgs classifier scores of the samples and optimize the boundaries that give the best combined significance. `categorization_2D.py`, on the other hand, takes both the Higgs classifier scores and the VBF classifier scores of the samples and optimizes the 2D boundaries that give the best combined significance.

```
python scripts/categorization_1D.py [-r REGION] [-f NUMBER OF FOLDS] [-b NUMBER OF CATEGORIES] [-n NSCAN] [--floatB] [--minN minN] [--skip]

Usage:
  -f, --fold          Number of folds of the categorization optimization. Default is 1.
  -b, --nbin          Number of BDT categories
  -n, --nscan         Number of scans. Default is 100
  --minN,             minN is the minimum number of events required in the mass window. The default is 5.
  --floatB            To float the last BDT boundary, which means to veto the lowest BDT score events
  --skip              To skip the hadd step (if you have already merged signal and background samples)
```

```
python scripts/categorization_2D.py [-r REGION] [-f NUMBER OF FOLDS] [-b NUMBER OF CATEGORIES] [-b NUMBER OF ggF CATEGORIES] [-n NSCAN] [--floatB] [--minN minN] [--skip]

Usage:
  -f, --fold          Number of folds of the categorization optimization. Default is 1.
  -b, --nbin          Number of BDT categories
  -n, --nscan         Number of scans. Default is 100
  --minN,             minN is the minimum number of events required in the mass window. The default is 5.
  --floatB            To float the last BDT boundary, which means to veto the lowest BDT score events
  --skip              To skip the hadd step (if you have already merged signal and background samples)
```

## Spurial signel test

For this step, there is no need to activate the conda analysis environment.

### Setup environment

Get the CMS env first. Please make sure you have enter `HiggsZGammaAna' directory.
```
scram project CMSSW CMSSW_11_3_4
cd CMSSW_11_3_4/src
cmsenv
```
There are another two package needed. And need to clone them from github.
```
git clone https://github.com/cms-analysis/HiggsAnalysis-CombinedLimit.git HiggsAnalysis/CombinedLimit -b 112x-comb2021
cd HiggsAnalysis/CombinedLimit/
cd ../../
git clone https://github.com/cms-analysis/CombineHarvester.git HiggsAnalysis/CombineHarvester
cd HiggsAnalysis/CombineHarvester/
git checkout v2.0.0
cd ../../
scram b -j 9
```
Please note that you need to initialize **each time you setup a terminal** by doing this.
```
cd CMSSW_11_3_4/src
cmsenv
```

### Scripts to run a task
