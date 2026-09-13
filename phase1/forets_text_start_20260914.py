"""Untuned third-task interface preparation, not registered in active searches."""

TASK='spooky-author-identification'
PROTOCOL='word_tfidf_lr_text_common_v1'


def code_for(task):
    if task!=TASK:raise ValueError('unregistered text task')
    return '''import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import log_loss
train = pd.read_csv('./data/train.csv')
test = pd.read_csv('./data/test.csv')
y = train['author'].astype(str)
X = train[['text']].copy()
Z = test[['text']].copy()
X['text'] = X['text'].fillna('').astype(str)
Z['text'] = Z['text'].fillna('').astype(str)

def build_model(X):
    from sklearn.compose import ColumnTransformer
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    preprocess = ColumnTransformer([
        ('text', TfidfVectorizer(ngram_range=(1, 2), min_df=2,
            max_features=50000, sublinear_tf=True), 'text')
    ])
    return make_pipeline(preprocess, LogisticRegression(C=1.0, max_iter=1000,
        solver='lbfgs', random_state=0))

model = build_model(X)
X_train, X_valid, y_train, y_valid = train_test_split(
    X, y, test_size=0.2, random_state=0, stratify=y)
model.fit(X_train, y_train)
print('Validation log loss:', log_loss(y_valid,
    model.predict_proba(X_valid), labels=model.classes_))
model.fit(X, y)
out = pd.DataFrame(model.predict_proba(Z), columns=model.classes_)
out.insert(0, 'id', test['id'].to_numpy())
out.to_csv('submission.csv', index=False)
print('Common starting model wrote submission.csv')
'''
