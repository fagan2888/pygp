"""
Basic demo showing how to instantiate a simple GP model, add data to it, and
optimize its hyperparameters.
"""

# global imports.
import os
import numpy as np
import matplotlib.pyplot as pl

# local imports
import pygp
import pygp.priors
import pygp.plotting as pp


if __name__ == '__main__':
    # load the data.
    cdir = os.path.abspath(os.path.dirname(__file__))
    data = np.load(os.path.join(cdir, 'xy.npz'))
    X = data['X']
    y = data['y']

    # create the model and add data to it.
    model = pygp.BasicGP(sn=.1, sf=1, ell=.1)
    model.add_data(X, y)

    # find the ML hyperparameters and plot the predictions.
    pygp.optimize(model)

    # create a prior structure.
    priors = dict(
        sn=pygp.priors.Uniform(0.01, 1.0),
        sf=pygp.priors.Uniform(0.01, 5.0),
        ell=pygp.priors.Uniform(0.01, 1.0))

    # create sample-based models.
    mcmc = pygp.meta.MCMC(model, priors, n=200, burn=100)
    smc = pygp.meta.SMC(model, priors, n=200)

    pl.figure(1)
    pl.clf()

    pl.subplot(131)
    pp.plot_posterior(model)
    pl.axis(ymin=-3, ymax=3)
    pl.title('Type-II ML')
    pl.legend(loc='best')

    pl.subplot(132)
    pp.plot_posterior(mcmc)
    pl.axis(ymin=-3, ymax=3)
    pl.title('MCMC')

    pl.subplot(133)
    pp.plot_posterior(mcmc)
    pl.axis(ymin=-3, ymax=3)
    pl.title('SMC')
    pl.draw()
    pl.show()
