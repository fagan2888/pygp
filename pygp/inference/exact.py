"""
Implementation of exact latent-function inference in a Gaussian process model
for regression.
"""

# future imports
from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

# global imports
import numpy as np
import scipy.linalg as sla

# local imports
from ._base import GP
from ..likelihoods import Gaussian
from ..utils.exceptions import ModelError

# exported symbols
__all__ = ['ExactGP']


class ExactGP(GP):
    def __init__(self, likelihood, kernel):
        # XXX: exact inference will only work with Gaussian likelihoods.
        if not isinstance(likelihood, Gaussian):
            raise ModelError('exact inference requires a Gaussian likelihood')

        super(ExactGP, self).__init__(likelihood, kernel)
        self._R = None
        self._a = None

    def _update(self):
        sn2 = np.exp(self._likelihood._logsigma*2)
        K = self._kernel.get(self._X) + sn2 * np.eye(len(self._X))
        y = self._y
        self._R = sla.cholesky(K)
        self._a = sla.solve_triangular(self._R, y, trans=True)

    def _updateinc(self, X, y):
        sn2 = np.exp(self._likelihood._logsigma*2)
        Kss = self._kernel.get(X) + sn2 * np.eye(len(X))
        Kxs = self._kernel.get(self._X, X)
        y = y
        self._R, self._a = chol_update(self._R, Kxs, Kss, self._a, y)

    def _posterior(self, X):
        # grab the prior mean and covariance.
        mu = np.zeros(X.shape[0])
        Sigma = self._kernel.get(X)

        if self._X is not None:
            K = self._kernel.get(self._X, X)
            V = sla.solve_triangular(self._R, K, trans=True)

            # add the contribution to the mean coming from the posterior and
            # subtract off the information gained in the posterior from the
            # prior variance.
            mu += np.dot(V.T, self._a)
            Sigma -= np.dot(V.T, V)

        return mu, Sigma

    def posterior(self, X, grad=False):
        # grab the prior mean and variance.
        mu = np.zeros(X.shape[0])
        s2 = self._kernel.dget(X)

        if self._X is not None:
            K = self._kernel.get(self._X, X)
            V = sla.solve_triangular(self._R, K, trans=True)

            # add the contribution to the mean coming from the posterior and
            # subtract off the information gained in the posterior from the
            # prior variance.
            mu += np.dot(V.T, self._a)
            s2 -= np.sum(V**2, axis=0)

        if not grad:
            return (mu, s2)

        # Get the prior gradients. Note that this assumes a constant mean and
        # stationary kernel.
        dmu = np.zeros_like(X)
        ds2 = np.zeros_like(X)

        if self._X is not None:
            dK = self._kernel.gradx(X, self._X)  # (ntest, ndata, dim)
            ntest, dim = X.shape
            dK = np.rollaxis(dK, 1)              # (ndata, ntest, dim)
            dK = np.reshape(dK, (self.ndata, ntest * dim))

            RiK = sla.solve_triangular(self._R, K, trans=True)
            RidK = sla.solve_triangular(self._R, dK, trans=True)

            dmu = np.dot(RidK.T, self._a)
            dmu = np.reshape(dmu, (ntest, dim))
            RidK = np.reshape(RidK, (self.ndata, ntest, dim))
            RidK = np.rollaxis(RidK, 2)
            ds2 = -2 * np.sum(RidK * RiK, axis=1).T

        return (mu, s2, dmu, ds2)

    def loglikelihood(self, grad=False, n=np.inf):
        """
        Compute the log likelihood of last `n` data points conditioned on the
        rest of the observations.
        """
        if n >= self.ndata:
            a = self._a
            R = self._R
            n = self.ndata

        else:
            # unpack already computed cholesky into relevant blocks
            A = self._R[:n, :n]
            B = self._R[:n, -n:]
            R = self._R[-n:, -n:]

            # compute the conditional mean
            mu = sla.solve_triangular(A, self._y[:n], trans=True)
            mu = np.dot(B.T, mu)

            # subtract the conditional mean from the last `n` observed points
            # and solve for a in: Ra = y_n - mu
            a = sla.solve_triangular(R, self._y[-n:] - mu, trans=True)

        lZ = -0.5 * np.inner(a, a)
        lZ -= 0.5 * np.log(2 * np.pi) * n
        lZ -= np.sum(np.log(R.diagonal()))

        # bail early if we don't need the gradient.
        if not grad:
            return lZ

        # FIXME -- Bobak: Gradient will not work with n < self.ndata

        # intermediate terms.
        alpha = sla.solve_triangular(self._R, self._a, trans=False)
        Q = sla.cho_solve((self._R, False), np.eye(self.ndata))
        Q -= np.outer(alpha, alpha)

        dlZ = np.r_[
            # derivative wrt the likelihood's noise term.
            -np.exp(self._likelihood._logsigma*2) * np.trace(Q),

            # derivative wrt each kernel hyperparameter.
            [-0.5*np.sum(Q*dK)
              for dK in self._kernel.grad(self._X)]]

        return lZ, dlZ


def chol_update(A, B, C, a, b):
    n = A.shape[0]
    m = C.shape[0]

    B = sla.solve_triangular(A, B, trans=True)
    C = sla.cholesky(C - np.dot(B.T, B))
    c = np.dot(B.T, a)

    # grow the new cholesky and use then use this to grow the vector a.
    A = np.r_[np.c_[A, B], np.c_[np.zeros((m,n)), C]]
    a = np.r_[a, sla.solve_triangular(C, b-c, trans=True)]

    return A, a
