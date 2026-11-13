"""Combine hard-max BCE auxiliary gradients with a strict pre-clip cap."""
import math

import torch

CAP_RATIO = 0.10


def norm(grads):
    present = [g.detach().float().reshape(-1) for g in grads if g is not None]
    return torch.cat(present).norm().item() if present else 0.0


def backward_capped(trans_node_loss, auxiliary_loss, params, base_weight, *, capture=False):
    """Expect original-side node gradients in .grad; add trans node then capped auxiliary."""
    params = tuple(p for p in params if p.requires_grad)
    assert all(p.dtype == torch.float32 for p in params)
    if not math.isfinite(base_weight) or base_weight < 0:
        raise ValueError('invalid auxiliary weight')
    raw = torch.autograd.grad(auxiliary_loss, params, allow_unused=True, retain_graph=True)
    trans_node_loss.backward()
    node = tuple(p.grad for p in params)
    nn, an = norm(node), norm(raw)
    if not math.isfinite(nn) or not math.isfinite(an):
        raise ValueError('nonfinite node or auxiliary gradients')
    weight = min(base_weight, CAP_RATIO*nn/an) if an else base_weight
    scaled = tuple(g.detach().float()*weight if g is not None and weight and an else None for g in raw)
    capped_norm = norm(scaled)
    # Apply any FP32 norm rounding correction before touching the accumulated gradients.
    if nn and (capped_norm > CAP_RATIO*nn or capped_norm/nn > CAP_RATIO):
        correction = (CAP_RATIO*nn/capped_norm) * (1 - 2*torch.finfo(torch.float32).eps)
        weight *= correction
        scaled = tuple(g*correction if g is not None else None for g in scaled)
        capped_norm = norm(scaled)
    assert capped_norm <= CAP_RATIO*nn and (not nn or capped_norm/nn <= CAP_RATIO)
    detail = dict(node_norm=nn, raw_aux_norm=an, effective_weight=weight, capped_aux_norm=capped_norm,
                  aux_to_node=capped_norm/nn if nn else 0.0, cap_active=weight < base_weight)
    if capture:
        detail['expected'] = tuple(g.detach().clone() if a is None and g is not None else
                                   a.detach().clone() if g is None and a is not None else
                                   g + a if g is not None else None for g, a in zip(node, scaled))
    with torch.no_grad():
        for p, g in zip(params, scaled):
            if g is not None:
                if p.grad is None:
                    p.grad = g
                else:
                    p.grad.add_(g)
    return detail
