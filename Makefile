##################################################################################
# GLOBALS                                                                       #
#################################################################################

PROJECT_DIR := $(shell dirname $(realpath $(lastword $(MAKEFILE_LIST))))
BUCKET = [OPTIONAL] your-bucket-for-syncing-data (do not include 's3://')
PROFILE = default
PROJECT_NAME = tweet_classification
PYTHON_INTERPRETER = python3
REGION = europe-west1

ifeq (,$(shell which conda))
HAS_CONDA=False
else
HAS_CONDA=True
endif

#################################################################################
# COMMANDS                                                                      #
#################################################################################

## Install Python Dependencies
requirements: test_environment
	$(PYTHON_INTERPRETER) -m pip install -U pip setuptools wheel
	$(PYTHON_INTERPRETER) -m pip install -r requirements.txt

## Make Dataset
data: requirements
	$(PYTHON_INTERPRETER) src/data/make_dataset.py data/raw data/processed

## Make train
train: requirements
	$(PYTHON_INTERPRETER) src/models/train_model.py 

## Make predict
predict: requirements
	$(PYTHON_INTERPRETER) src/models/predict_model.py 
	
## Predict tweet
api: 
	curl -X 'GET' 'https://tweet-classification-app-ed4ieygz7a-ew.a.run.app/tweet/'$(tweet) -H 'accept: application/json'

## test
do :
    @echo "What is your age?: "; \
    read AGE; \
    echo "Your age is ", $$(AGE)

# ## Make visualize
# visualize: requirements
# 	$(PYTHON_INTERPRETER) src/visualization/visualize.py models/trained_model.pt 

# ## Make docker build train
# docker_build_train: requirements
# 	$(PYTHON_INTERPRETER) docker build -f train.dockerfile . -t $(PROJECT_NAME)/train:latest

# ## Make docker build test
# docker_build_test: requirements
# 	$(PYTHON_INTERPRETER) docker build -f test.dockerfile . -t $(PROJECT_NAME)/inference:latest

# ## Make docker tag 
# docker_tag: requirements
# 	$(PYTHON_INTERPRETER) docker tag tester gcr.io/braided-destiny-374308/$(PROJECT_NAME)

# ## Make docker push 
# docker_push:requirements
# 	$(PYTHON_INTERPRETER) docker push gcr.io/braided-destiny-374308/$(PROJECT_NAME)

## Make run job train
run_job_train: requirements
	gcloud ai custom-jobs create --region=$(REGION) --display-name=train-run --config=config_cpu_train.yaml

## Make run job test
run_job_inference: requirements
	gcloud ai custom-jobs create --region=$(REGION) --display-name=inference-run --config=config_cpu_inference.yaml

## Make deploy api
deploy_api: requirements
	gcloud run deploy tweet-classification-app --region=$(REGION) --image gcr.io/braided-destiny-374308/$(PROJECT_NAME)/api:latest --platform managed --allow-unauthenticated --memory 8Gi --cpu 2
## Delete all compiled Python files
clean:
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete

## Lint using flake8
lint:
	flake8 src

## Set up python interpreter environment
create_environment:
ifeq (True,$(HAS_CONDA))
		@echo ">>> Detected conda, creating conda environment."
ifeq (3,$(findstring 3,$(PYTHON_INTERPRETER)))
	conda create --name $(PROJECT_NAME) python=3
else
	conda create --name $(PROJECT_NAME) python=2.7
endif
		@echo ">>> New conda env created. Activate with:\nsource activate $(PROJECT_NAME)"
else
	$(PYTHON_INTERPRETER) -m pip install -q virtualenv virtualenvwrapper
	@echo ">>> Installing virtualenvwrapper if not already installed.\nMake sure the following lines are in shell startup file\n\
	export WORKON_HOME=$$HOME/.virtualenvs\nexport PROJECT_HOME=$$HOME/Devel\nsource /usr/local/bin/virtualenvwrapper.sh\n"
	@bash -c "source `which virtualenvwrapper.sh`;mkvirtualenv $(PROJECT_NAME) --python=$(PYTHON_INTERPRETER)"
	@echo ">>> New virtualenv created. Activate with:\nworkon $(PROJECT_NAME)"
endif

## Test python environment is setup correctly
test_environment:
	$(PYTHON_INTERPRETER) test_environment.py

#################################################################################
# PROJECT RULES                                                                 #
#################################################################################



#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

.DEFAULT_GOAL := help

# Inspired by <http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html>
# sed script explained:
# /^##/:
# 	* save line in hold space
# 	* purge line
# 	* Loop:
# 		* append newline + line to hold space
# 		* go to next line
# 		* if line starts with doc comment, strip comment character off and loop
# 	* remove target prerequisites
# 	* append hold space (+ newline) to line
# 	* replace newline plus comments by `---`
# 	* print line
# Separate expressions are necessary because labels cannot be delimited by
# semicolon; see <http://stackoverflow.com/a/11799865/1968>
.PHONY: help
help:
	@echo "$$(tput bold)Available rules:$$(tput sgr0)"
	@echo
	@sed -n -e "/^## / { \
		h; \
		s/.*//; \
		:doc" \
		-e "H; \
		n; \
		s/^## //; \
		t doc" \
		-e "s/:.*//; \
		G; \
		s/\\n## /---/; \
		s/\\n/ /g; \
		p; \
	}" ${MAKEFILE_LIST} \
	| LC_ALL='C' sort --ignore-case \
	| awk -F '---' \
		-v ncol=$$(tput cols) \
		-v indent=19 \
		-v col_on="$$(tput setaf 6)" \
		-v col_off="$$(tput sgr0)" \
	'{ \
		printf "%s%*s%s ", col_on, -indent, $$1, col_off; \
		n = split($$2, words, " "); \
		line_length = ncol - indent; \
		for (i = 1; i <= n; i++) { \
			line_length -= length(words[i]) + 1; \
			if (line_length <= 0) { \
				line_length = ncol - indent - length(words[i]) - 1; \
				printf "\n%*s ", -indent, " "; \
			} \
			printf "%s ", words[i]; \
		} \
		printf "\n"; \
	}' \
	| more $(shell test $(shell uname) = Darwin && echo '--no-init --raw-control-chars')
