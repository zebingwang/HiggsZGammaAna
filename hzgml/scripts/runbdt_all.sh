#!/bin/bash
#########################################################################
#                                                                       #
#    The example wrapper for the training and categorization task.      #
#                                                                       #
#    Please contact ~jay.chan@cern.ch~ in case there is any issue.      #
#                                                                       #
#########################################################################

echo $#
if [ $# == 1 ]
then
    A=$1; S=-1;
else 
    S=-1; A=-1;
fi
echo "==================================================="
echo "num: $2"
echo "==================================================="
echo "Shielded parameter is: $S . Added variables is: $A ."
############################
#  Training the BDT models
############################
# python scripts/train_bdt.py -r zero_jet --save -s $S -a $A
# python scripts/train_bdt.py -r one_jet --save -s $S -a $A
# python scripts/train_bdt.py -r two_jet --save -s $S -a $A
# python scripts/train_bdt.py -r VBF --save -s $S -a $A
# python scripts/train_bdt.py -r VH_ttH --save -s $S -a $A

###########################################
#  Applying the BDT models to all samples
###########################################
# python scripts/apply_bdt.py -r zero_jet -s $S -a $A
# python scripts/apply_bdt.py -r one_jet -s $S -a $A
# python scripts/apply_bdt.py -r two_jet -s $S -a $A
# python scripts/apply_bdt.py -r VH_ttH -s $S -a $A

###########################################################
#  Optimizing the BDT boundaries for zero-jet and two-jet
###########################################################
# python scripts/categorization_1D.py -r zero_jet -b 4 -s $S -a $A --minN 300
# python scripts/categorization_1D.py -r one_jet -b 4 -s $S -a $A --minN 300
# python scripts/categorization_1D.py -r two_jet -b 4 -s $S -a $A --minN 200
python scripts/categorization_1D.py -r two_jet -b 4 --minN 200
# python scripts/categorization_1D.py -r VH_ttH -b 2 -s $S -a $A --minN 20

##############################################
#  Optimizing the BDT boundaries for two-jet
##############################################
# python scripts/categorization_2D.py -r two_jet -b 4 -v 4 -s $S

# zero_jet one_jet two_jet VH_ttH

# for i in zero_jet one_jet two_jet VH_ttH;
# do
# root -l -q 'scripts/draw_bdtDis.cpp("'$i'", 0, 1)';
# root -l -q 'scripts/draw_HMassDis.cpp("'$i'", 1)';
# root -l -q 'scripts/draw_HMassDis_sum.cpp("'$i'", 1)';
# done


