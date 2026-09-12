"""Fixed untuned common start, executed and charged inside each search budget."""
import hashlib

PROTOCOL = 'rf_common_v1'
PREFIX = '''import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OrdinalEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import log_loss, accuracy_score
train = pd.read_csv('./data/train.csv')
test = pd.read_csv('./data/test.csv')
'''
TAIL = '''categorical = list(X.select_dtypes(include=['object', 'category', 'bool']).columns)
numeric = [c for c in X.columns if c not in categorical]
for c in categorical:
    X[c] = X[c].fillna('__MISSING__').astype(str)
    Z[c] = Z[c].fillna('__MISSING__').astype(str)
preprocess = ColumnTransformer([
    ('num', SimpleImputer(strategy='median'), numeric),
    ('cat', OrdinalEncoder(handle_unknown='use_encoded_value', unknown_value=-1), categorical)
])
model = make_pipeline(preprocess, RandomForestClassifier(n_estimators=100, max_depth=12, random_state=0, n_jobs=6))
'''


def code_for(task):
    if task == 'leaf-classification':
        body = "y = train['species'].astype(str)\nX = train.drop(columns=['id', 'species']).copy()\nZ = test.drop(columns=['id']).copy()\n"
        end = "out = pd.DataFrame(model.predict_proba(Z), columns=model.classes_)\nout.insert(0, 'id', test['id'].to_numpy())\nout.to_csv('submission.csv', index=False)\n"
        metric = "print('Validation log loss:', log_loss(y_valid, model.predict_proba(X_valid), labels=model.classes_))\n"
    elif task == 'spaceship-titanic':
        body = "y = train['Transported'].astype(str).str.lower().map({'true': 1, 'false': 0})\nassert not y.isna().any()\ny = y.astype(int)\nX = train.drop(columns=['PassengerId', 'Name', 'Transported']).copy()\nZ = test.drop(columns=['PassengerId', 'Name']).copy()\n"
        end = "out = pd.DataFrame({'PassengerId': test['PassengerId'], 'Transported': model.predict(Z).astype(bool)})\nout.to_csv('submission.csv', index=False)\n"
        metric = "print('Validation accuracy:', accuracy_score(y_valid, model.predict(X_valid)))\n"
    else:
        raise ValueError('unregistered common-start task')
    validation = "X_train, X_valid, y_train, y_valid = train_test_split(X, y, test_size=0.2, random_state=0, stratify=y)\nmodel.fit(X_train, y_train)\n"
    return PREFIX + body + TAIL + validation + metric + "model.fit(X, y)\n" + end + "print('Common starting model wrote submission.csv')\n"


def initial(solver, path):
    protocol = getattr(solver.cfg, 'common_start_protocol', 'none')
    if protocol not in ('none', PROTOCOL):
        raise ValueError('unknown common start')
    active = protocol == PROTOCOL and solver.state.current_step == 1
    if active and (len(path) != 1 or path[0].parents):
        raise ValueError('common start must be the first root expansion')
    return active


def make_node(task, node_type):
    code = code_for(task)
    return node_type(code=code, plan='Fixed common starting program; no score-based selection or LLM generation.',
        parents=[], operators_used=['fixed_common_start'], operators_metrics=[])


def digest(task):
    return hashlib.sha256(code_for(task).encode()).hexdigest()
