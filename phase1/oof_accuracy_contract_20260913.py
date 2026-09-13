"""Explicit row-indexed training-CV accuracy; no model, test labels or repair API."""
from numbers import Integral


class OOFAccuracy:
    def __init__(self, labels):
        self.labels=list(labels)
        if not self.labels or any(x not in (0,1) for x in self.labels):raise ValueError('binary task labels required')
        self.values={}

    def add(self, row_indices, predicted_labels):
        indices=list(row_indices);predictions=list(predicted_labels)
        if len(indices)!=len(predictions) or not indices:raise ValueError('prediction/index length')
        if any(not isinstance(i,Integral) or isinstance(i,bool) or not 0<=i<len(self.labels) for i in indices):
            raise ValueError('original row indices required')
        if len(set(indices))!=len(indices) or any(int(i) in self.values for i in indices):raise ValueError('duplicate OOF row')
        if any(p not in (0,1) for p in predictions):raise ValueError('binary predicted labels required')
        # Validate the whole update before mutating state.
        self.values.update({int(i):int(p) for i,p in zip(indices,predictions)})

    def score(self):
        if len(self.values)!=len(self.labels):raise ValueError('incomplete OOF coverage')
        return sum(self.values[i]==label for i,label in enumerate(self.labels))/len(self.labels)

    def marker(self):
        return 'FINAL_VALIDATION_SCORE: '+repr(self.score())
