"""Task-specific prepared-data converters."""

from dojo.tasks.mlebench.warmup.converters.chaii import convert_chaii
from dojo.tasks.mlebench.warmup.converters.salt import convert_salt
from dojo.tasks.mlebench.warmup.converters.dogs import convert_dogs
from dojo.tasks.mlebench.warmup.converters.tensorflow import convert_tensorflow

CONVERTERS = {
    "chaii-hindi-and-tamil-question-answering": convert_chaii,
    "tgs-salt-identification-challenge": convert_salt,
    "dog-breed-identification": convert_dogs,
    "tensorflow2-question-answering": convert_tensorflow,
}
