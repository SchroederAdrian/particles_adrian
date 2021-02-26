#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
First numerical experiment in Waste-Free SMC paper (TODO)

Compare IBIS and SMC tempering for approximating:

* the normalising constant (marginal likelihood)
* the posterior expectation of the p coefficients

for a logistic regression model.

See below for how to select the dataset.
"""

from matplotlib import pyplot as plt
import numpy as np
from numpy import random
import seaborn as sb

import particles
from particles import datasets as dts
from particles import distributions as dists
from particles import resampling as rs
from particles import smc_samplers as ssps
from particles.collectors import Moments

datasets = {'pima': dts.Pima, 'eeg': dts.Eeg, 'sonar': dts.Sonar}
dataset_name = 'pima'  # choose one of the three
data = datasets[dataset_name]().data
T, p = data.shape

# Standard SMC: N is number of particles, K is number of MCMC steps
# Waste-free SMC: M is number of resampled particles, P is length of MCMC
# chains (same notations as in the paper)
# All of the runs are such that N*K or M*P equal 10^5

if dataset_name == 'sonar':
    N0 = 10**5
    Ks = [10, 40, 160]
    Ms = [50, 200, 800]
elif dataset_name == 'pima':
    N0 = 10**4
    Ks = [1, 4, 16]
    Ms = [25, 100, 400]
elif dataset_name == 'eeg':
    N0 = 10 ** 4
    Ks = [1, 4, 16]
    Ms = [25, 100, 400]

# prior & model
prior = dists.StructDist({'beta':dists.MvNormal(scale=5.,
                                                cov=np.eye(p))})

class LogisticRegression(ssps.StaticModel):
    def logpyt(self, theta, t):
        # log-likelihood factor t, for given theta
        lin = np.matmul(theta['beta'], data[t, :])
        return - np.logaddexp(0., -lin)

# algorithms
# N and values of M set above according to dataset
nruns = 50  # TODO
results = []

# runs
print('Dataset: %s' % dataset_name)
for M, K in zip(Ms, Ks):
    for i in range(nruns):
        # need to shuffle the data for IBIS
        random.shuffle(data)
        model = LogisticRegression(data=data, prior=prior)
        for alg_type in ['tempering', 'ibis']:
            for waste in [True, False]:
                if waste:
                    P = N0 // M
                    N, nsteps = M, P - 1
                    res = {'M': M, 'P': P}
                else:
                    N = N0 // K
                    nsteps = K
                    res = {'N': N, 'K': K}
                if alg_type == 'ibis':
                    fk = ssps.IBIS(model=model, nsteps=nsteps, wastefree=waste)
                else:
                    fk = ssps.AdaptiveTempering(model=model, nsteps=nsteps, 
                                                wastefree=waste)
                pf = particles.SMC(fk=fk, N=N, collect=[Moments], verbose=False)
                print('%s, waste:%i, nsteps=%i, run %i' % (alg_type, waste,
                                                           nsteps, i))
                pf.run()
                print('CPU time (min): %.2f' % (pf.cpu_time / 60))
                print('loglik: %f' % pf.logLt)
                res.update({'type': alg_type, 
                            'out': pf.summaries,
                            'waste': waste,
                            'cpu': pf.cpu_time})
                results.append(res)


# plots
#######
savefigs = True  # do you want to save figures as pdfs
plt.style.use('ggplot')
pal = sb.dark_palette('white', n_colors=2)


titles = ['standard SMC', 'waste-free SMC']
plots = {'log marginal likelihood': lambda rout: rout.logLts[-1],
         'post expectation first pred': 
         lambda rout: rout.moments[-1]['mean']['beta'][1]
        }

for plot, func in plots.items():
    fig, axs = plt.subplots(1, 2, sharey=True)
    for title, ax in zip(titles, axs):
        if title == 'waste-free SMC':
            rez = [r for r in results if r['waste']]
            xlab = 'M'
            ylab = ''
        else:
            rez = [r for r in results if not r['waste']]
            xlab = 'K'
            ylab = plot
        sb.boxplot(x=[r[xlab] for r in rez],
                   y=[func(r['out']) for r in rez],
                   hue=[r['type'] for r in rez],
                   palette=pal, ax=ax)
        ax.set(xlabel=xlab, title=title, ylabel=ylab)
        fig.tight_layout()
    if savefigs:
        fig.savefig('%s_boxplots_%s.pdf' % (dataset_name, plot))

