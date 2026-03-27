"""
RF Tomography — ISTA-based spatial occupancy reconstruction. (Phase 3-4)

Uses Iterative Shrinkage-Thresholding Algorithm (ISTA) with L1 regularisation
to reconstruct a 2-D occupancy grid from per-link CSI amplitude measurements.

References:
    - Beck & Teboulle (2009) "A Fast Iterative Shrinkage-Thresholding Algorithm"
    - Kaltiokallio et al. (2012) "Non-parametric RSS-based localization"
"""
from __future__ import annotations

import numpy as np


def _build_sensing_matrix(grid_size: tuple[int, int],
                          node_positions: list[tuple[float, float]]) -> np.ndarray:
    """Build the sensing matrix A where A[link, pixel] = path weight.

    Each link is a TX-RX pair.  The weight for a pixel on a link follows a
    simplified elliptical (Fresnel-inspired) model: pixels close to the
    line-of-sight path get weight 1, others 0 (binary mask with margin d0).
    """
    rows, cols = grid_size
    n = len(node_positions)
    n_links = n * (n - 1)          # directed pairs
    n_pixels = rows * cols

    A = np.zeros((n_links, n_pixels), dtype=np.float32)
    link_idx = 0

    # Grid pixel centres, normalised to unit square
    xs = np.linspace(0.0, 1.0, cols)
    ys = np.linspace(0.0, 1.0, rows)
    px, py = np.meshgrid(xs, ys)
    px = px.ravel()
    py = py.ravel()

    d0 = 0.5 / max(rows, cols)     # half-pixel margin (Fresnel width proxy)

    for i, (tx_x, tx_y) in enumerate(node_positions):
        for j, (rx_x, rx_y) in enumerate(node_positions):
            if i == j:
                continue
            tx = np.array([tx_x, tx_y], dtype=np.float64)
            rx = np.array([rx_x, rx_y], dtype=np.float64)
            link_len = np.linalg.norm(rx - tx) + 1e-9
            pts = np.stack([px, py], axis=1)   # (n_pix, 2)
            d_tx = np.linalg.norm(pts - tx, axis=1)
            d_rx = np.linalg.norm(pts - rx, axis=1)
            # Pixels inside the first Fresnel zone (ellipse with foci at TX/RX)
            excess = d_tx + d_rx - link_len
            A[link_idx] = (excess < d0).astype(np.float32)
            link_idx += 1

    return A


def _soft_threshold(v: np.ndarray, thresh: float) -> np.ndarray:
    """Element-wise soft-thresholding operator."""
    return np.sign(v) * np.maximum(np.abs(v) - thresh, 0.0)


class RFTomography:
    """ISTA-based RF tomography for spatial occupancy grid reconstruction.

    Parameters
    ----------
    grid_size : (rows, cols)
        Resolution of the output occupancy grid.
    lambda_reg : float
        L1 regularisation strength (sparsity penalty).
    max_iter : int
        Maximum ISTA iterations.
    tol : float
        Convergence tolerance on the update norm.
    """

    def __init__(self,
                 grid_size: tuple[int, int] = (10, 10),
                 lambda_reg: float = 0.1,
                 max_iter: int = 200,
                 tol: float = 1e-5) -> None:
        self.grid_size = grid_size
        self.lambda_reg = lambda_reg
        self.max_iter = max_iter
        self.tol = tol
        self._grid: np.ndarray = np.zeros(grid_size, dtype=np.float32)

    # ------------------------------------------------------------------
    def reconstruct(self,
                    csi_matrix: np.ndarray,
                    node_positions: list[tuple[float, float]]) -> np.ndarray:
        """Reconstruct occupancy grid via ISTA L1 solver.

        Parameters
        ----------
        csi_matrix : ndarray, shape (n_nodes, n_subcarriers) or (n_links,)
            CSI amplitude observations.  If 2-D, per-node mean is taken as
            the per-link measurement vector after pairing.
        node_positions : list of (x, y) in [0, 1]^2
            Normalised positions of the WiFi nodes in the room.

        Returns
        -------
        ndarray, shape grid_size
            Estimated occupancy probability per pixel (values in [0, 1]).
        """
        if len(node_positions) < 2:
            raise ValueError("At least 2 nodes required for tomography.")

        A = _build_sensing_matrix(self.grid_size, node_positions)  # (L, P)

        # Build measurement vector y from csi_matrix
        csi_arr = np.asarray(csi_matrix, dtype=np.float64)
        if csi_arr.ndim == 2:
            node_means = np.mean(np.abs(csi_arr), axis=1)  # (n_nodes,)
            n = len(node_positions)
            y = []
            for i in range(n):
                for j in range(n):
                    if i != j:
                        y.append((node_means[i] + node_means[j]) / 2.0)
            y = np.array(y, dtype=np.float64)
        else:
            y = csi_arr.ravel().astype(np.float64)
            if y.shape[0] != A.shape[0]:
                # Pad or truncate to match sensing matrix
                target = A.shape[0]
                if y.shape[0] < target:
                    y = np.pad(y, (0, target - y.shape[0]))
                else:
                    y = y[:target]

        # Normalise
        y_norm = y - y.mean()
        y_std = y.std() + 1e-9
        y_norm /= y_std

        # ISTA: minimise 0.5 * ||Ax - y||^2 + lambda * ||x||_1
        AtA = A.T @ A                          # (P, P)
        Aty = A.T @ y_norm                     # (P,)
        lip = float(np.linalg.norm(AtA, ord=2)) + 1e-9   # Lipschitz const
        step = 1.0 / lip
        x = np.zeros(A.shape[1], dtype=np.float64)

        for _ in range(self.max_iter):
            grad = AtA @ x - Aty
            x_new = _soft_threshold(x - step * grad, self.lambda_reg * step)
            delta = np.linalg.norm(x_new - x)
            x = x_new
            if delta < self.tol:
                break

        # Map to [0, 1] and reshape
        x = np.clip(x, 0.0, None)
        x_max = x.max()
        if x_max > 0:
            x /= x_max
        self._grid = x.reshape(self.grid_size).astype(np.float32)
        return self._grid

    # ------------------------------------------------------------------
    def visualize(self) -> dict:
        """Return serialisable grid data for frontend rendering."""
        grid = self._grid
        return {
            "grid": grid.tolist(),
            "rows": self.grid_size[0],
            "cols": self.grid_size[1],
            "max_value": float(grid.max()),
            "mean_value": float(grid.mean()),
            "occupied_cells": int((grid > 0.5).sum()),
        }
