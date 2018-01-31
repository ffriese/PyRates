"""Pytest test file for ...
"""

import numpy as np
import pytest
import pickle


###########
# Utility #
###########

from core.utility import nmrse


def setup_module():
    print("\n")
    print("================================")
    print("| Test Suite 4 : Circuit Class |")
    print("================================")


#########
# Tests #
#########


# noinspection PyTypeChecker
@pytest.mark.xfail
def test_4_1_jr_circuit_i():
    """Tests whether current implementation shows expected behavior when standard Jansen-Rit circuit ([1]_)is fed
    with step-function input targeted onto the excitatory interneurons.

    See Also
    --------
    :class:`JansenRitCircuit`: Documentation of Jansen-Rit NMM parametrization
    :class:`NeuralMassModel`: Detailed documentation of NMM parameters, attributes and methods.

    References
    ----------
    .. [1] B.H. Jansen & V.G. Rit, "Electroencephalogram and visual evoked potential generation in a mathematical model
       of coupled cortical columns." Biological Cybernetics, vol. 73(4), pp. 357-366, 1995.

    """

    from core.circuit import JansenRitCircuit

    # set parameters
    ################

    N = 3
    n_synapses = 2
    max_synaptic_delay = 0.15  # s

    # simulations parameters
    simulation_time = 1.0  # s
    step_size = 5e-4  # s

    # synaptic inputs
    start_stim = 0.3  # s
    len_stim = 0.05  # s
    mag_stim = 200.0  # 1/s

    synaptic_inputs = np.zeros((int(simulation_time / step_size), N, n_synapses))
    synaptic_inputs[int(start_stim / step_size):int(start_stim / step_size + len_stim / step_size), 1, 0] = mag_stim

    # initialize neural mass network
    ################################

    circuit = JansenRitCircuit(step_size=step_size, max_synaptic_delay=max_synaptic_delay)

    # run network simulation
    ########################

    # print('| Test VII - Jansen-Rit Circuit |')

    circuit.run(synaptic_inputs=synaptic_inputs,
                simulation_time=simulation_time)

    states = circuit.get_population_states(state_variable_idx=0) - 0.075

    # load target data
    ##################

    with open('../resources/JR_results_I.pickle', 'rb') as f:
        target_states = pickle.load(f)

    # calculate nmrse between time-series
    #####################################

    error = nmrse(states[1:, :], target_states)
    error = np.mean(error)

    # perform unit test
    ###################

    # test response to step-function input to EINs
    assert pytest.approx(0, abs=0.5) == error


@pytest.mark.xfail
def test_4_2_jr_circuit_ii():
    """
    Tests whether current implementation shows expected behavior when standard Jansen-Rit circuit is fed with step-
    function input to the excitatory interneurons plus constant input to the pyramidal cells.
    """

    from core.circuit import JansenRitCircuit

    # set parameters
    ################

    # circuit parameters
    N = 3
    n_synapses = 2

    # simulations parameters
    simulation_time = 1.0  # s
    cutoff_time = 0.0  # s
    step_size = 5.0e-4  # s

    # synaptic inputs
    start_stim = 0.3  # s
    len_stim = 0.05  # s
    mag_stim = 300.0  # 1/s

    synaptic_inputs = np.zeros((int(simulation_time / step_size), N, n_synapses))
    synaptic_inputs[int(start_stim / step_size):int(start_stim / step_size + len_stim / step_size), 1, 0] = mag_stim
    synaptic_inputs[:, 0, 0] = mag_stim / 3.

    # initialize neural mass network
    ################################

    nmm = JansenRitCircuit(max_synaptic_delay=0.045)

    # run network simulation
    ########################

    nmm.run(synaptic_inputs=synaptic_inputs,
            simulation_time=simulation_time)

    states = nmm.get_population_states(state_variable_idx=0)

    # load target data
    ###################

    with open('../resources/JR_results_II.pickle', 'rb') as f:
        target_states = pickle.load(f)

    # calculate nmrse between time-series
    #####################################

    error = nmrse(states[1:, :], target_states.T)
    error = np.mean(error)

    # perform unit test
    ###################

    # test response to step-function input to EINs plus constant input to PCs
    assert pytest.approx(0, abs=0.5) == error


# noinspection PyTypeChecker
@pytest.mark.skip
def test_4_3_jr_circuit_iii():
    """
    Tests whether expected bifurcation occurs when synaptic efficiency of JR circuit is altered (given constant
    input).
    This test actually succeeds but takes too long. It is also not clear whether the result correct or not.
    """

    from core.circuit import CircuitFromScratch

    # set parameters
    ################

    # simulations parameters
    simulation_time = 3.0  # s
    cutoff_time = 0.0  # s
    step_size = 5.0e-4  # s

    # populations
    population_labels = ['PC', 'EIN', 'IIN']
    N = len(population_labels)
    n_synapses = 2

    # synapses
    connections = np.zeros((N, N, n_synapses))

    # AMPA connections (excitatory)
    connections[:, :, 0] = [[0, 0.8 * 135, 0], [1.0 * 135, 0, 0], [0.25 * 135, 0, 0]]

    # GABA-A connections (inhibitory)
    connections[:, :, 1] = [[0, 0, 0.25 * 135], [0, 0, 0], [0, 0, 0]]

    gaba_a_dict = {'efficacy': 0.5 * 1.273 * -1e-12,  # A
                   'tau_decay': 0.02,  # s
                   'tau_rise': 0.0004,  # s
                   'conductivity_based': False}

    max_synaptic_delay = 0.05  # s

    # axon
    axon_dict = {'max_firing_rate': 5.,  # 1/s
                 'membrane_potential_threshold': -0.069,  # V
                 'sigmoid_steepness': 555.56}  # 1/V
    axon_params = [axon_dict for i in range(N)]

    init_states = np.zeros(N)

    # synaptic inputs
    mag_stim = 200.0  # 1/s
    synaptic_inputs = np.zeros((int(simulation_time / step_size), N, n_synapses))
    synaptic_inputs[:, 1, 0] = mag_stim

    # loop over different AMPA synaptic efficiencies and simulate network behavior
    ##############################################################################

    ampa_efficiencies = np.linspace(0.1, 1.0, 20) * 1.273 * 3e-13

    final_state = np.zeros(len(ampa_efficiencies))

    for i, efficiency in enumerate(ampa_efficiencies):
        # set ampa parameters
        #####################

        ampa_dict = {'efficacy': float(efficiency),  # A
                     'tau_decay': 0.006,  # s
                     'tau_rise': 0.0006,  # s
                     'conductivity_based': False}

        synapse_params = [ampa_dict, gaba_a_dict]

        # initialize neural mass network
        ################################

        nmm = CircuitFromScratch(connectivity=connections,
                                 step_size=step_size,
                                 synapse_params=synapse_params,
                                 axon_params=axon_params,
                                 max_synaptic_delay=max_synaptic_delay,
                                 init_states=init_states,
                                 population_labels=population_labels,
                                 delays=None)

        # run network simulation
        ########################

        nmm.run(synaptic_inputs=synaptic_inputs,
                simulation_time=simulation_time)

        final_state[i] = nmm.get_population_states(state_variable_idx=0)[-1, 0]

    # load target data
    ###################

    with open('../resources/JR_results_III.pickle', 'rb') as f:
        target_states = pickle.load(f)

    # calculate nmrse between time-series
    #####################################

    error = nmrse(final_state, target_states)
    error = np.mean(error)

    # perform unit test
    ###################

    # test response to varying AMPA synapse efficiencies given constant input to EINs.
    assert pytest.approx(0, abs=0.5) == error


def test_4_4_jr_network_i():
    """
    tests whether 2 delay-connected vs unconnected JR circuits behave as expected.
    """

    # set parameters
    ################

    # connectivity matrices
    inter_circuit_conns = np.array([[0, 1], [0, 0]]) * 100.
    C1 = np.zeros((2, 2, 2))
    C2 = np.zeros((2, 2, 2))
    C2[:, :, 0] = inter_circuit_conns

    # delay matrix
    D = np.zeros((2, 2))
    D[0, 1] = 0.001
    D[1, 0] = 0.001

    # neural mass circuits
    from core.circuit import JansenRitCircuit
    nmm1 = JansenRitCircuit()
    nmm2 = JansenRitCircuit()
    nmm3 = JansenRitCircuit()
    nmm4 = JansenRitCircuit()

    # simulation step-size
    step_size = 5e-4

    # simulation time
    simulation_time = 1.
    timesteps = np.int(simulation_time / step_size)

    # synaptic input
    stim_time = 0.3
    stim_timesteps = np.int(stim_time / step_size)
    synaptic_input = np.zeros((timesteps, 6, 2))
    synaptic_input[0:stim_timesteps, 1, 0] = 300.

    # initialize nmm network
    ########################
    from core.circuit import CircuitFromCircuit
    circuit1 = CircuitFromCircuit(circuits=[nmm1, nmm2],
                                  connectivity=C1,
                                  delays=D,
                                  circuit_labels=['NMM1', 'NMM2'])
    circuit2 = CircuitFromCircuit(circuits=[nmm3, nmm4],
                                  connectivity=C2,
                                  delays=D,
                                  circuit_labels=['NMM1', 'NMM2'])

    # run network simulations
    #########################

    circuit1.run(synaptic_inputs=synaptic_input, simulation_time=simulation_time)
    circuit2.run(synaptic_inputs=synaptic_input, simulation_time=simulation_time)

    # perform unit tests
    ####################

    states1 = circuit1.get_population_states(state_variable_idx=0)
    states2 = circuit2.get_population_states(state_variable_idx=0)

    error = nmrse(states1, states2)
    error = np.mean(error)

    # test information transfer between two delay-connected JR circuits...
    assert not pytest.approx(0, abs=0.5) == error