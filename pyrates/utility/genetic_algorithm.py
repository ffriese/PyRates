# -*- coding: utf-8 -*-
#
#
# PyRates software framework for flexible implementation of neural
# network model_templates and simulations. See also:
# https://github.com/pyrates-neuroscience/PyRates
#
# Copyright (C) 2017-2018 the original authors (Richard Gast and
# Daniel Rose), the Max-Planck-Institute for Human Cognitive Brain
# Sciences ("MPI CBS") and contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>
#
# CITATION:
#
# Richard Gast and Daniel Rose et. al. in preparation

# external imports
import numpy as np
import pandas as pd
from typing import Optional

# system imports
import random
from itertools import cycle

from pyrates.utility.grid_search import grid_search, ClusterGridSearch, linearize_grid

# meta infos
__author__ = "Christoph Salomon, Richard Gast"
__status__ = "development"


class GeneticAlgorithmTemplate:
    def __init__(self, initial_gene_pool: dict):

        # self.fitness_func = cdist
        self.initial_gene_pool = initial_gene_pool
        self.num_genes = len(initial_gene_pool)

        # Initialize storage variables
        self.sigma_adapt = 0
        self.gene_names = []
        self.pop = pd.DataFrame()
        self.pop_size = 0
        self.candidate = pd.DataFrame()
        self.current_max_fitness = 0
        self.winner = pd.DataFrame()

        self.__create_pop()

    def run(self, target: list, max_iter: int, min_fit: Optional[float] = 0., n_winners: Optional[int] = 1,
            n_parents: Optional[int] = 10, n_new: Optional[int] = 0, sigma_adapt: Optional[float] = 0.,
            max_stagnation_steps: Optional[int] = 0, stagnation_decimals: Optional[int] = 8,
            enforce_max_iter: Optional[bool] = False,  candidate_save: Optional[str] = "", **kwargs):
        """

        Parameters
        ----------
        target
        max_iter
        min_fit
        n_winners
        n_parents
        n_new
        sigma_adapt
        max_stagnation_steps
        stagnation_decimals
        enforce_max_iter
        candidate_save
        kwargs


        Returns
        -------

        """

        if n_winners + n_parents + n_new > self.pop_size:
            print('WARNING: Sum of winners, parents and new members exceeds the population size. Returning')
            return

        self.sigma_adapt = sigma_adapt

        # Start genetic algorithm
        #########################
        print("***STARTING GENETIC ALGORITHM***")
        iter_count = 0
        stagnation_count = 0
        while iter_count < max_iter:
            print(f'ITERATION: {iter_count}')

            # Evaluate fitness of current population
            ########################################
            self.eval_fitness(target, **kwargs)
            new_candidate = self.pop.nlargest(1, "fitness")
            self.current_max_fitness = float(new_candidate.loc[:, "fitness"])
            print(f'Current max fitness: {self.current_max_fitness}')

            # Check for fitness stagnation
            ##############################
            # TODO: Abbruchkriterium auf Basis der Stagnation?
            if max_stagnation_steps > 0:
                if not self.candidate.empty:
                    old_fitness = np.round(float(self.candidate['fitness']), decimals=stagnation_decimals)
                    new_fitness = np.round(self.current_max_fitness, decimals=stagnation_decimals)
                    if new_fitness == old_fitness:
                        stagnation_count += 1
                        if stagnation_count > max_stagnation_steps:
                            print("Maximum fitness stagnation reached!")
                            print("Dropping fittest from population!")
                            self.pop = self.pop.drop(new_candidate.index)
                    else:
                        # Reset stagnation counter
                        stagnation_count = 0

            # Update candidate and save if necessary
            ########################################
            self.candidate = new_candidate
            if candidate_save:
                self.candidate.to_hdf(candidate_save, key='data')

            # Update currently winning genes
            ################################
            if self.winner.empty:
                self.winner = self.candidate
            elif float(self.candidate['fitness']) > float(self.winner['fitness']):
                self.winner = self.candidate

            # Evaluate minimum fitness conversion criteria
            ##############################################
            if 0 < min_fit < self.current_max_fitness and not enforce_max_iter:
                return self.winner

            # Create offspring from current population
            ##########################################
            self.__create_offspring(n_parents=n_parents, n_new=n_new, n_winners=n_winners)
            iter_count += 1

        # End of iteration loop
        print("Maximum iterations reached")
        if float(self.winner['fitness']) < min_fit:
            print('Could not satisfy minimum fitness condition.')
        return self.winner

    def __create_offspring(self, n_winners, n_parents=0, n_new=0):
        """Create a new offspring of the current population

        Offspring contains:
        - n_winners strongest members of the current population (winners)
        - n_parents Children of current parent pairings (crossover)
        - N Mutations of winners and children (mutations)
        - n_new Fresh members based on the initial gene pool (new)

        The number of mutations is chosen dynamically to resize the offspring to the size of the current population
        """
        print('Updating population')

        # Create new offspring
        #####################
        offspring = []
        new_sigs = []
        n_mutations = self.pop_size - (n_parents + n_new + n_winners)

        # 1. Add n_winners strongest members
        ####################################
        winners = self.__select_winners(n_winners=n_winners)
        for w in winners:
            offspring.append(w[0])
            new_sigs.append(w[1])

        # 2. Add children of n_parents parent pairs
        ###########################################
        parent_pairs = self.__create_parent_pairs(n_parent_pairs=n_parents)
        try:
            childs = self.__crossover(parent_pairs)
            for c in childs:
                offspring.append(c[0])
                new_sigs.append(c[1])
        except ValueError:
            n_mutations += n_parents

        # 3. Add mutations
        ##################
        parent_pool = cycle(zip(offspring, new_sigs))
        for mut in range(n_mutations):
            parent = next(parent_pool)
            mutation = self.__mutate(parent)
            offspring.append(mutation[0])
            new_sigs.append(mutation[1])

        # 4. Add n_new fresh members from initial gene_pool
        ###################################################
        for n in range(n_new):
            new_member = self.__create_new_member()
            offspring.append(new_member[0])
            new_sigs.append(new_member[1])

        offspring = pd.DataFrame(offspring)
        offspring['fitness'] = 0.0
        offspring['sigma'] = new_sigs
        offspring.columns = self.pop.columns

        self.pop = offspring

    def __create_pop(self):
        """Create new base population based on the parameters provided in self.pop_genes"""
        # Empty population
        pop_grid = {}
        # self.pop = pd.DataFrame()

        for param, value in self.initial_gene_pool.items():
            self.gene_names.append(param)
            pop_grid[param] = np.linspace(value['min'], value['max'], value['N'])
        self.pop = linearize_grid(pop_grid, permute=True)
        self.pop_size = self.pop.shape[0]

        sigmas = [self.initial_gene_pool[gene]['sigma'] for gene in self.initial_gene_pool.keys()]

        self.pop['fitness'] = 0.0
        self.pop['sigma'] = [sigmas for _ in range(self.pop_size)]

    def __select_winners(self, n_winners):
        """Choose the n_winners fittest members from the current population"""
        winners = []
        for idx in self.pop.nlargest(n_winners, 'fitness').index:
            winner_genes = self.pop.iloc[idx].drop(['fitness', 'sigma']).to_list()
            winner_sigma = self.pop.iloc[idx]['sigma']
            winners.append([winner_genes, winner_sigma])
        return winners

    def __mutate(self, parent):
        """Create a mutation of a parent, based on a gaussian distribution for each gene"""
        mu_new = []
        sigma_new = []
        for i, (mu, sigma) in enumerate(zip(parent[0], parent[1])):
            mu_temp = mu + np.random.randn() * sigma
            while any([mu_temp < self.initial_gene_pool[self.gene_names[i]]['min'],
                       mu_temp > self.initial_gene_pool[self.gene_names[i]]['max']]):
                mu_temp = mu+np.random.randn()*sigma
            mu_new.append(mu_temp)
            # Adapt sigma (Beyer1995, p.5)
            xi = np.exp(self.sigma_adapt*np.random.randn())
            sigma_new.append(sigma*xi)
        return mu_new, sigma_new

    def __create_new_member(self):
        """Create a new population member from pop_params"""
        genes = []
        sigma = []
        for i, (key, value) in enumerate(self.initial_gene_pool.items()):
            genes.append(random.uniform(value['min'], value['max']))
            sigma.append(value['sigma'])
        new_member = [genes, sigma]
        already_exists = (self.pop.drop(['fitness', 'sigma'], axis=1) == new_member[0]).all(1).any()
        if already_exists:
            new_member = self.__create_new_member()
        return new_member

    def __create_parent_pairs(self, n_parent_pairs):
        """Create n_parent_pairs parent-parent tuples. The occurrence probability is based on the parent's fitness"""
        parents = []
        parent_repro = self.pop['fitness'].to_numpy()
        parent_repro = np.nan_to_num(parent_repro, copy=True)
        parent_repro /= parent_repro.sum()

        parent_indices = self.pop.index.values
        for n in range(n_parent_pairs):
            p_idx = list(np.random.choice(parent_indices, size=(2,), replace=False, p=parent_repro))
            parents.append((self.pop.iloc[p_idx[0], :], self.pop.iloc[p_idx[1], :]))
        return parents

    def __crossover(self, parent_pairs, n_tries=5):
        """Create a child from each parent pair. Each child gene is uniformly chosen from its parents

        If the child already exists in the current population, new genes are chosen, but maximal n_tries times before a
        ValueError is raised.
        """
        childs = []
        for parents in parent_pairs:
            count = 0
            while True:
                if count > n_tries:
                    raise ValueError
                child_genes = []
                child_sigma = []
                for g, gene in enumerate(self.initial_gene_pool):
                    choice = np.random.uniform()
                    if choice > 0.5:
                        child_genes.append(parents[0][gene])
                        child_sigma.append(parents[0]['sigma'][g])
                    else:
                        child_genes.append(parents[1][gene])
                        child_sigma.append(parents[1]['sigma'][g])
                already_exists = (self.pop.drop(['fitness', 'sigma'], axis=1) == child_genes).all(1).any()
                if not already_exists:
                    break
                count += 1
            childs.append((child_genes, child_sigma))
        return childs

    def eval_fitness(self, target: list, *argv, **kwargs):
        raise NotImplementedError


class GSGeneticAlgorithm(GeneticAlgorithmTemplate):
    from scipy.spatial.distance import cdist

    def __init__(self, initial_gene_pool, gs_config, fitness_measure=cdist):
        super().__init__(initial_gene_pool)

        self.fitness_measure = fitness_measure
        self.gs_config = gs_config

    def eval_fitness(self, target: list, **kwargs):
        param_grid = self.pop.drop(['fitness', 'sigma'], axis=1)

        results = grid_search(circuit_template=self.gs_config['circuit_template'],
                              param_grid=param_grid,
                              param_map=self.gs_config['param_map'],
                              simulation_time=self.gs_config['simulation_time'],
                              dt=self.gs_config['dt'],
                              sampling_step_size=self.gs_config['sampling_step_size'],
                              permute_grid=False,
                              inputs=self.gs_config['inputs'],
                              outputs=self.gs_config['outputs'].copy()
                              )

        for i, candidate_genes in enumerate(param_grid.values):
            candidate_out = results.loc[:, tuple(candidate_genes)].values.T

            target_reshaped = np.array(target)[None, :]
            dist = self.fitness_measure(candidate_out, target_reshaped)
            self.pop.at[i, 'fitness'] = float(1 / dist)


class CGSGeneticAlgorithm(GeneticAlgorithmTemplate):
    def __init__(self, initial_gene_pool, gs_config, cgs_config):
        super().__init__(initial_gene_pool)

        self.gs_config = gs_config
        self.cgs_config = cgs_config

        self.cgs = ClusterGridSearch(cgs_config['nodes'], compute_dir=cgs_config['compute_dir'])

    def eval_fitness(self, target: list, **kwargs):

        param_grid = self.pop.drop(['fitness', 'sigma'], axis=1)

        res_file = self.cgs.run(
            circuit_template=self.gs_config['circuit_template'],
            params=param_grid,
            param_map=self.gs_config['param_map'],
            simulation_time=self.gs_config['simulation_time'],
            dt=self.gs_config['dt'],
            inputs=self.gs_config['inputs'],
            outputs=self.gs_config['outputs'],
            sampling_step_size=self.gs_config['sampling_step_size'],
            permute=False,
            chunk_size=self.cgs_config['chunk_size'],
            worker_env=self.cgs_config['worker_env'],
            worker_file=self.cgs_config['worker_file'],
            config_kwargs={
                'target': target
            })

        results = pd.read_hdf(res_file, key=f'/Results/fitness')

        for i, candidate_genes in enumerate(param_grid.values):
            self.pop.at[i, 'fitness'] = float(results.loc['fitness', tuple(candidate_genes)])




