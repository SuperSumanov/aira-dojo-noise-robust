import sys
from pathlib import Path
import pandas as pd
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_forets_current_pool_20260912 import independent_accuracy, independent_leaf_loss


def fixtures():
    return (pd.DataFrame({'PassengerId':['b','a'],'Transported':['False','True']}),
            pd.DataFrame({'PassengerId':['a','b'],'Transported':[True,False]}))


def test_ids_not_row_order_and_boolean_format():
    pred,truth=fixtures();assert independent_accuracy(pred,truth)==1
    pred.loc[0,'Transported']='True';assert independent_accuracy(pred,truth)==.5


@pytest.mark.parametrize('failure',['duplicate','bad_label','nan','different_id','missing_column'])
def test_invalid_input_fails_closed(failure):
    pred,truth=fixtures()
    if failure=='duplicate':pred['PassengerId']=['a','a']
    if failure=='bad_label':pred['Transported']=['yes','no']
    if failure=='nan':pred.loc[0,'Transported']=None
    if failure=='different_id':pred['PassengerId']=['x','a']
    if failure=='missing_column':pred=pred.drop(columns='Transported')
    with pytest.raises(ValueError):independent_accuracy(pred,truth)


def test_accuracy_ignores_extra_columns_and_accepts_binary_numeric():
    pred,truth=fixtures();pred['Transported']=[0,1];pred['extra']=123
    assert independent_accuracy(pred,truth)==1


def test_leaf_tolerance_does_not_silently_renormalize():
    truth=pd.DataFrame({'id':[2,1],'a':[0,1],'b':[1,0]})
    pred=pd.DataFrame({'id':[1,2],'b':[.3000005,.8],'a':[.7,.2]})
    assert independent_leaf_loss(pred,truth)==pytest.approx(-(np.log(.7)+np.log(.8))/2,abs=1e-14)


def test_leaf_zero_clipping():
    truth=pd.DataFrame({'id':[1,2],'a':[1,0],'b':[0,1]})
    pred=pd.DataFrame({'id':[1,2],'a':[0.,1.],'b':[1.,0.]})
    assert independent_leaf_loss(pred,truth)==pytest.approx(-np.log(np.finfo(float).eps))
