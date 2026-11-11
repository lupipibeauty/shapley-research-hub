import numpy as np
import pytest

from aggregate_report_shapley.fgsv_ablation import STAGES, fgsv_sequential_ablation


class Utility:
    def __init__(self, weights): self.weights=list(weights); self.calls=0
    def __call__(self, selection):
        self.calls+=1
        return sum(self.weights[int(i)] for i in selection)


@pytest.mark.parametrize("n,weights,group,truth",[(2,[1.,4.],[0],1.),(3,[1.,1.,4.],[0,1],2.)])
def test_corrected_normalization_is_exact_for_controlled_additive_games(n,weights,group,truth):
    for stage in STAGES[1:]:
        u=Utility(weights)
        result=fgsv_sequential_ablation(u,n,group,200,np.random.RandomState(7),10,stage)
        assert result["estimate"] == pytest.approx(truth,abs=1e-12)
        assert u.calls==200


def test_a0_exposes_missing_small_branch_normalization_for_n2():
    u=Utility([1.,4.])
    result=fgsv_sequential_ablation(u,2,[0],50,np.random.RandomState(7),10,STAGES[0])
    assert result["estimate"] == pytest.approx(1.75,abs=1e-12)
