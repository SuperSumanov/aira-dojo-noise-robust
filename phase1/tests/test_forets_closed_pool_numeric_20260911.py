import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_forets_closed_pool_20260911 import independent_loss

def test_id_and_column_alignment():
    a=pd.DataFrame({'id':[2,1],'a':[0,1],'b':[1,0]})
    p=pd.DataFrame({'b':[.1,.8],'id':[1,2],'a':[.9,.2]})
    assert independent_loss(p,a)==pytest.approx(-(np.log(.9)+np.log(.8))/2)

@pytest.mark.parametrize('failure',['duplicate','missing_class','invalid_probs'])
def test_invalid_regrade_fails_closed(failure):
    a=pd.DataFrame({'id':[1,2],'a':[1,0],'b':[0,1]});p=a.copy()
    if failure=='duplicate':p['id']=[1,1]
    if failure=='missing_class':p=p.drop(columns='b')
    if failure=='invalid_probs':p['a']=2
    with pytest.raises(ValueError):independent_loss(p,a)
