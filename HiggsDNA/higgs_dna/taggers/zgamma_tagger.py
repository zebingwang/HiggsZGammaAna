import awkward
import time
import numpy
import numba
import vector

vector.register_awkward()

import logging
logger = logging.getLogger(__name__)

from higgs_dna.taggers.tagger import Tagger, NOMINAL_TAG 
from higgs_dna.utils import awkward_utils, misc_utils
from higgs_dna.selections import object_selections, lepton_selections, jet_selections, tau_selections, physics_utils
from higgs_dna.selections import gen_selections

DUMMY_VALUE = -999.
DEFAULT_OPTIONS = {
    "photons" : {
        "use_central_nano" : True,
        "pt" : 15.0,
        "eta" : [
            [0.0, 1.4442],
            [1.566, 2.5]
        ],
        "mvaID_barrel" : -0.4,
        "mvaID_endcap" : -0.58,
        "e_veto" : 0.5
    },
    "zgammas" : {
        "relative_pt_gamma" : 0.1363636363636364,
        "mass_h" : [100., 180.],
        "mass_sum" : 185,
        "select_highest_pt_sum" : True
    },
    "trigger" : {
        "2016" : ["HLT_Ele23_Ele12_CaloIdL_TrackIdL_IsoVL_DZ", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass8"],
        "2016UL_preVFP" : ["HLT_Ele23_Ele12_CaloIdL_TrackIdL_IsoVL_DZ", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass8"],
        "2016UL_postVFP" : ["HLT_Ele23_Ele12_CaloIdL_TrackIdL_IsoVL_DZ", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass8"],
        "2017" : ["HLT_Ele23_Ele12_CaloIdL_TrackIdL_IsoVL_DZ", "HLT_Ele23_Ele12_CaloIdL_TrackIdL_IsoVL", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass8", " HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ", "HLT_Mu17_TrkIsoVVL_TkMu8_TrkIsoVVL_DZ"],
        "2018" : ["HLT_Ele23_Ele12_CaloIdL_TrackIdL_IsoVL_DZ", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass3p8", "HLT_Mu17_TrkIsoVVL_Mu8_TrkIsoVVL_DZ_Mass8"]
    },
    "electrons" : {
        "pt" : 7.0
    },
    "muons" : {
        "pt" : 5.0
    },
    "jets" : {
        "pt" : 30.0,
        "eta" : 4.7,
        "dr_photons" : 0.4,
        "dr_electrons" : 0.4,
        "dr_muons" : 0.4,
    },
    "gen_info" : {
        "calculate" : False,
        "max_dr" : 0.2,
        "max_pt_diff" : 15.
    }  
}


# Diphoton preselection below synced with flashgg, see details in:
#   - https://indico.cern.ch/event/1071721/contributions/4551056/attachments/2320292/3950844/HiggsDNA_DiphotonPreselectionAndSystematics_30Sep2021.pdf

class ZGammaTagger(Tagger):
    def __init__(self, name = "default_zgamma_tagger", options = {}, is_data = None, year = None):
        super(ZGammaTagger, self).__init__(name, options, is_data, year)

        if not options:
            self.options = DEFAULT_OPTIONS
        else:
            self.options = misc_utils.update_dict(
                    original = DEFAULT_OPTIONS,
                    new = options
            )


    def calculate_selection(self, events):
        """
        Select photons and create diphoton pairs.
        Add a record "Diphoton" to events array with relevant information about each diphoton pair.
        In principle, there can be more than one Diphoton pair per event.
        """

        # Determine what type of rho variable is available in nanoAOD
        # To be deleted once a standard rho variable is added to central nanoAOD
        if not self.options["photons"]["use_central_nano"]:
            if "fixedGridRhoAll" in events.fields:
                rho = events.fixedGridRhoAll
            elif "fixedGridRhoFastjetAll" in events.fields:
                rho = events.fixedGridRhoFastjetAll
            elif "Rho_fixedGridRhoAll" in events.fields:
                rho = events.Rho_fixedGridRhoAll
        else:
            rho = awkward.ones_like(events.Photon)

        photon_selection = self.select_photons(
                photons = events.Photon,
                rho = rho,
                options = self.options["photons"]
        )

        zgamma_selection, zgammas = self.produce_and_select_zgammas(
                events = events,
                photons = events.Photon[photon_selection],
                options = self.options["zgammas"]
        )

        if not self.is_data and self.options["gen_info"]["calculate"]:
            zgammas = self.calculate_gen_info(zgammas, self.options["gen_info"])

        return zgamma_selection, zgammas 


    def produce_and_select_zgammas(self, events, photons, options):
        """
        Perform diphoton preselection.
        For events with more than 2 photons, more than 1 diphoton candidate
        per event is possible.

        :param events: events array to calculate diphoton candidates from
        :type events: awkward.highlevel.Array
        :param photons: array of selected photons from events
        :type photons: awkward.highlevel.Array
        :param options: dictionary containing configurable options for the diphoton preselection
        :type options: dict
        :return: boolean array indicating which events pass the diphoton preselection
        :rtype: awkward.highlevel.Array
        """

        start = time.time()

        # Electrons
        electron_cut = lepton_selections.select_electrons(
            electrons = events.Electron,
            options = self.options["electrons"],
            clean = {
            },
            name = "SelectedElectron",
            tagger = self
        )

        electrons = awkward_utils.add_field(
            events = events,
            name = "SelectedElectron",
            data = events.Electron[electron_cut]
        )

        # Muons
        muon_cut = lepton_selections.select_muons(
            muons = events.Muon,
            options = self.options["muons"],
            clean = {
            },
            name = "SelectedMuon",
            tagger = self
        )

        muons = awkward_utils.add_field(
            events = events,
            name = "SelectedMuon",
            data = events.Muon[muon_cut]
        )

        # Jets
        jet_cut = jet_selections.select_jets(
            jets = events.Jet,
            options = self.options["jets"],
            clean = {
                "photons" : {
                    "objects" : photons,
                    "min_dr" : self.options["jets"]["dr_photons"]
                },
                "electrons" : {
                    "objects" : electrons,
                    "min_dr" : self.options["jets"]["dr_electrons"]
                },
                "muons" : {
                    "objects" : muons,
                    "min_dr" : self.options["jets"]["dr_muons"]
                }
            },
            name = "SelectedJet",
            tagger = self
        )

        jets = awkward_utils.add_field(
            events = events,
            name = "SelectedJet",
            data = events.Jet[jet_cut]
        )

        # Add object fields to events array
        for objects, name in zip([electrons, muons, jets], ["electron", "muon", "jet"]):
            awkward_utils.add_object_fields(
                events = events,
                name = name,
                objects = objects,
                n_objects = 4,
                dummy_value = DUMMY_VALUE
            )

        n_electrons = awkward.num(electrons)
        N_e_cut = n_electrons>=2
        awkward_utils.add_field(events, "n_electrons", n_electrons, overwrite=True)

        n_muons = awkward.num(muons)
        N_mu_cut = n_muons>=2
        awkward_utils.add_field(events, "n_muons", n_muons, overwrite=True)

        n_leptons = n_electrons + n_muons
        N_e_mu_cut = N_e_cut | N_mu_cut
        awkward_utils.add_field(events, "n_leptons", n_leptons, overwrite=True)

        n_jets = awkward.num(jets)
        awkward_utils.add_field(events, "n_jets", n_jets, overwrite=True)

        # Make trigger cuts 
        if self.year is not None:
            trigger_cut = awkward.num(events.Photon) < 0 # dummy cut, all False
            for hlt in self.options["trigger"][self.year]: # logical OR of all triggers
                if hasattr(events, hlt):
                    trigger_cut = (trigger_cut) | (events[hlt] == True)
        else:
            trigger_cut = awkward.num(events.Photon) >= 0 # dummy cut, all True

        # PDG ID
        electrons = awkward.with_field(electrons, awkward.ones_like(electrons.pt) * 11, "id")
        muons = awkward.with_field(muons, awkward.ones_like(muons.pt) * 13, "id")

        # Sort objects by pt
        photons = photons[awkward.argsort(photons.pt, ascending=False, axis=1)]
        electrons = electrons[awkward.argsort(electrons.pt, ascending=False, axis=1)]
        muons = muons[awkward.argsort(muons.pt, ascending=False, axis=1)]

        # Register as `vector.Momentum4D` objects so we can do four-vector operations with them
        photons = awkward.Array(photons, with_name = "Momentum4D")
        electrons = awkward.Array(electrons, with_name = "Momentum4D")
        muons = awkward.Array(muons, with_name = "Momentum4D")
        
        # Construct di-electron/di-muon pairs
        ee_pairs = awkward.combinations(electrons, 2, fields = ["LeadLepton", "SubleadLepton"])
        ee_cut1 = ee_pairs.LeadLepton.pt > 25
        ee_cut2 = ee_pairs.SubleadLepton.pt > 15
        ee_pairs = ee_pairs[ee_cut1&ee_cut2]
        ee_cut1 = awkward.sum(ee_cut1, axis=1) >= 1
        ee_cut2 = awkward.sum(ee_cut2, axis=1) >= 1

        mm_pairs = awkward.combinations(muons, 2, fields = ["LeadLepton", "SubleadLepton"])
        mm_cut1 = mm_pairs.LeadLepton.pt > 20
        mm_cut2 = mm_pairs.SubleadLepton.pt > 10
        mm_pairs = mm_pairs[mm_cut1&mm_cut2]
        mm_cut1 = awkward.sum(mm_cut1, axis=1) >= 1
        mm_cut2 = awkward.sum(mm_cut2, axis=1) >= 1

        # Have gamma candidate events level cut
        N_g_cut = awkward.num(photons)>=1

        # Concatenate these together
        z_cands = awkward.concatenate([ee_pairs, mm_pairs], axis = 1)
        z_cands["ZCand"] = z_cands.LeadLepton + z_cands.SubleadLepton # these add as 4-vectors since we registered them as "Momentum4D" objects

        # Make Z candidate-level cuts
        os_cut = z_cands.LeadLepton.charge * z_cands.SubleadLepton.charge == -1
        mass_cut = (z_cands.ZCand.mass > 50.)
        z_cut = os_cut & mass_cut
        z_cands = z_cands[z_cut] # OSSF lepton pairs with m_ll > 50.
        
        has_z_cand = awkward.num(z_cands) >= 1
        z_cands = z_cands[awkward.argsort(abs(z_cands.ZCand.mass - 91.1876), axis = 1)] # take the one with mass closest to mZ
        z_cand = awkward.firsts(z_cands)

        # Add Z-related fields to array
        for field in ["pt", "eta", "phi", "mass", "charge", "id"]:
            if not field in ["charge", "id"]:
                awkward_utils.add_field(
                        events,
                        "Z_%s" % field,
                        awkward.fill_none(getattr(z_cand.ZCand, field), DUMMY_VALUE)
                )
            awkward_utils.add_field(
                    events,
                    "Z_lead_lepton_%s" % field,
                    awkward.fill_none(z_cand.LeadLepton[field], DUMMY_VALUE)
            )
            awkward_utils.add_field(
                    events,
                    "Z_sublead_lepton_%s" % field,
                    awkward.fill_none(z_cand.SubleadLepton[field], DUMMY_VALUE)
            )

        # lepton-photon overlap removal 
        clean_photon_mask = object_selections.delta_R(photons, muons, 0.4) & object_selections.delta_R(photons, electrons, 0.4)
        photons = photons[clean_photon_mask]

        # Make gamma candidate-level cuts
        has_gamma_cand = awkward.num(photons) >= 1
        gamma_cand = awkward.firsts(photons)

        # Add gamma-related fields to array
        for field in ["pt", "eta", "phi", "mass", "mvaID", "energyErr"]:
            awkward_utils.add_field(
                events,
                "gamma_%s" % field,
                awkward.fill_none(getattr(gamma_cand, field), DUMMY_VALUE)
            )

        # Make Higgs candidate-level cuts
        h_cand = (z_cand.ZCand + gamma_cand)
        sel_h_1 = (gamma_cand.pt / h_cand.mass) > options["relative_pt_gamma"]
        sel_h_2 = (z_cand.ZCand.mass + h_cand.mass) > options["mass_sum"]
        sel_h_3 = (h_cand.mass > options["mass_h"][0]) & (h_cand.mass < options["mass_h"][1])

        sel_h_1 = awkward.fill_none(sel_h_1, value = False)
        sel_h_2 = awkward.fill_none(sel_h_2, value = False)
        sel_h_3 = awkward.fill_none(sel_h_3, value = False)

        # Add Higgs-related fields to array
        for field in ["pt", "eta", "phi", "mass"]:
            awkward_utils.add_field(
                events,
                "H_%s" % field,
                awkward.fill_none(getattr(h_cand, field), DUMMY_VALUE)
            )

        # additional leptons
        additional_leptons = awkward.concatenate([electrons, muons], axis = 1)
        veto_Z_leptons = (additional_leptons.pt != events.Z_lead_lepton_pt) & (additional_leptons.pt != events.Z_sublead_lepton_pt)
        additional_leptons = additional_leptons[veto_Z_leptons]       
        additional_leptons = additional_leptons[awkward.argsort(additional_leptons.pt, ascending=False, axis=1)]

        for objects, name in zip([additional_leptons], ["additional_lepton"]):
            awkward_utils.add_object_fields(
                events = events,
                name = name,
                objects = objects,
                n_objects = 2,
                dummy_value = DUMMY_VALUE
            )

        for cut_type in ["zgammas", "zgammas_ele", "zgammas_mu", "zgammas_w", "zgammas_ele_w", "zgammas_mu_w"]:
            if "_w" in cut_type:
                if hasattr(events, 'genWeight'):
                    weighted = True
                else:
                    continue
            else:
                weighted = False

            cut0 = awkward.num(events.Photon) >= 0

            if "ele" in cut_type:
                cut1 = N_e_cut
            elif "mu" in cut_type:
                cut1 = N_mu_cut
            else:
                cut1 = N_e_mu_cut

            cut2 = cut1 & trigger_cut

            if "ele" in cut_type:
                cut3 = cut2 & ee_cut1
            elif "mu" in cut_type:
                cut3 = cut2 & mm_cut1
            else:
                cut3 = cut2 & (ee_cut1 | mm_cut1)

            if "ele" in cut_type:
                cut4 = cut3 & ee_cut2
            elif "mu" in cut_type:
                cut4 = cut3 & mm_cut2
            else:
                cut4 = cut3 & (ee_cut2 | mm_cut2)

            cut5 = cut4 & has_gamma_cand

            cut6 = cut5 & has_z_cand

            cut7 = cut6 & sel_h_1

            cut8 = cut7 & sel_h_2

            cut9 = cut8 & sel_h_3            

            self.register_event_cuts(
                names = ["all", "N_lep_sel", "trig_cut", "lead_lep_pt_cut", "sub_lep_pt_cut", "has_g_cand", "has_z_cand", "sel_h_1", "sel_h_2", "sel_h_3"],
                results = [cut0, cut1, cut2, cut3, cut4, cut5, cut6, cut7, cut8, cut9],
                events = events,
                cut_type = cut_type,
                weighted = weighted
            )
        
        all_cuts = trigger_cut & has_z_cand & has_gamma_cand & sel_h_1 & sel_h_2 & sel_h_3

        elapsed_time = time.time() - start
        logger.debug("[ZGammaTagger] %s, syst variation : %s, total time to execute select_zgammas: %.6f s" % (self.name, self.current_syst, elapsed_time))

        #dummy_cut =  awkward.num(events.Photon) >= 0
        return all_cuts, events 

    
    def calculate_gen_info(self, zgammas, options):
        """
        Calculate gen info, adding the following fields to the events array:
            GenHggHiggs : [pt, eta, phi, mass, dR]
            GenHggLeadPhoton : [pt, eta, phi, mass, dR, pt_diff]
            GenHggSubleadPhoton : [pt, eta, phi, mass, dR, pt_diff]
            LeadPhoton : [gen_dR, gen_pt_diff]
            SubleadPhoton : [gen_dR, gen_pt_diff]

        Perform both matching of
            - closest gen photons from Higgs to reco lead/sublead photons from diphoton candidate
            - closest reco photons to gen photons from Higgs

        If no match is found for a given reco/gen photon, it will be given values of -999. 
        """
        gen_hzg = gen_selections.select_x_to_yz(zgammas.GenPart, 25, 23, 22)
        
        awkward_utils.add_object_fields(
                events = zgammas,
                name = "GenHzgHiggs",
                objects = gen_hzg.GenParent,
                n_objects = 1
        )

        return zgammas 
        

    def select_photons(self, photons, rho, options):
        """
        Enforces all photon cuts that are commmon to both
        leading and subleading photons in the diphoton preselection.
        Cuts specific to a diphoton pair are not enforced here.

        :param photons: input collection of photons to use for calculating selected photons
        :type photons: awkward.highlevel.Array
        :param rho: energy density in each event, used for corrections to photon isolation cuts
        :type rho: awkward.highlevel.Array
        :param options: dictionary containing configurable options for the photon selection
        :type options: dict
        :return: boolean array indicating which photons pass the photon selection
        :rtype: awkward.highlevel.Array
        """
        # pt
        pt_cut = photons.pt > options["pt"]

        # eta
        #eta_cut = Tagger.get_range_cut(abs(photons.eta), options["eta"]) | (photons.isScEtaEB | photons.isScEtaEE)
        #eta_cut = (photons.isScEtaEB | photons.isScEtaEE)
        eta_cut = ((photons.isScEtaEB & (photons.mvaID > options["mvaID_barrel"])) | (photons.isScEtaEE & (photons.mvaID > options["mvaID_endcap"])))

        # electron veto
        e_veto_cut = photons.electronVeto > options["e_veto"]

        use_central_nano = options["use_central_nano"] # indicates whether we are using central nanoAOD (with some branches that are necessary for full diphoton preselection missing) or custom nanoAOD (with these branches added)


        all_cuts = pt_cut & eta_cut & e_veto_cut

        self.register_cuts(
                names = ["pt", "eta", "e_veto", "all"],
                results = [pt_cut, eta_cut, e_veto_cut, all_cuts],
                cut_type = "photon"
        )

        return all_cuts

# Below is an example of how the diphoton preselection could be performed with an explicit loop (C++ style) 
# that is compiled with numba for increased performance.

# NOTE: pre-compiled numba functions should be defined outside the class,
# as numba does not like when a class instance is passed to a function
@numba.njit
def produce_diphotons(photons, n_photons, lead_pt_cut, lead_pt_mgg_cut, sublead_pt_mgg_cut):
    n_events = len(photons)

    diphotons_offsets = numpy.zeros(n_events + 1, numpy.int64)
    diphotons_contents = []
    lead_photons_idx = []
    sublead_photons_idx = []

    # Loop through events and select diphoton pairs
    for i in range(n_events):
        n_diphotons_event = 0
        # Enumerate photon pairs
        if n_photons[i] >= 2: # only try if there are at least 2 photons
            sum_pt = 0
            for j in range(n_photons[i]):
                for k in range(j+1, n_photons[i]):
                    # Choose who is the leading photon
                    lead_idx = j if photons[i][j].pt > photons[i][k].pt else k
                    sublead_idx = k if photons[i][j].pt > photons[i][k].pt else j
                    lead_photon = photons[i][lead_idx]
                    sublead_photon = photons[i][sublead_idx]

                    # Lead photon must satisfy lead pt cut
                    if lead_photon.pt < lead_pt_cut:
                        continue

                    # Construct four vectors
                    lead_photon_vec = vector.obj(
                            pt = lead_photon.pt,
                            eta = lead_photon.eta,
                            phi = lead_photon.phi,
                            mass = lead_photon.mass
                    )
                    sublead_photon_vec = vector.obj(
                            pt = sublead_photon.pt,
                            eta = sublead_photon.eta,
                            phi = sublead_photon.phi,
                            mass = sublead_photon.mass
                    )
                    diphoton = vector.obj(px = 0., py = 0., pz = 0., E = 0.) # IMPORTANT NOTE: you need to initialize this to an empty vector first. Otherwise, you will get ZeroDivisionError exceptions for like 1 out of a million events (seemingly only with numba). 
                    diphoton = diphoton + lead_photon_vec + sublead_photon_vec

                    if (diphoton.mass < 100) | (diphoton.mass > 180):
                        continue

                    if lead_photon.pt / diphoton.mass < lead_pt_mgg_cut:
                        continue

                    if sublead_photon.pt / diphoton.mass < sublead_pt_mgg_cut:
                        continue

                    # This diphoton candidate passes
                    n_diphotons_event += 1

                    diphotons_contents.append([
                        diphoton.pt,
                        diphoton.eta,
                        diphoton.phi,
                        diphoton.mass
                    ])

                    lead_photons_idx.append(lead_idx)
                    sublead_photons_idx.append(sublead_idx)

        diphotons_offsets[i+1] = diphotons_offsets[i] + n_diphotons_event

    return diphotons_offsets, numpy.array(diphotons_contents), numpy.array(lead_photons_idx), numpy.array(sublead_photons_idx)
