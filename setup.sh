#TODO: some problems here. Seems break the environment after "cmsenv"
cd /afs/cern.ch/user/j/jiehan/private/HiggsZGammaAna/
conda deactivate
conda activate higgs-zg-ana
source /cvmfs/sft.cern.ch/lcg/views/LCG_104/x86_64-centos7-gcc12-opt/setup.sh
source /cvmfs/sft.cern.ch/lcg/releases/LCG_104/ROOT/6.28.04/x86_64-centos7-gcc12-opt/bin/thisroot.sh
cd /afs/cern.ch/user/j/jiehan/private/HiggsZGammaAna/SSTest/CMSSW_11_3_4/src/
cmsenv
cd /afs/cern.ch/user/j/jiehan/private/HiggsZGammaAna/