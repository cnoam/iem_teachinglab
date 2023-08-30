#!/bin/bash
# for 094290, 2023-10

/databricks/python/bin/pip install nltk spacy # These should be in the workspace libraries

# These files can be downloaded from default url, or we can prefill the cache dir or set alternate 
/databricks/python/bin/python -m nltk.downloader punkt stopwords wordnet averaged_perceptron_tagger vader_lexicon omw-1.4

/databricks/python/bin/python -m spacy download en_core_web_sm


