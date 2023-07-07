"""

### GLOBAL IMPORT SECTION ###

"""


import json
import os
import time
from enum import Enum
from abc import ABC, abstractmethod
from pathlib import Path
from functools import wraps
import pandas as pd
import numpy as np


"""

### CHART TYPE ###

"""


class CHART_TYPE(Enum):
    SCALAR = 'scalar'
    BARS = 'bars'
    BINS = 'bins'



"""

### SIMILARITY MODEL SECTION ###

"""


class SimilarityModel(ABC):

    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def similarity_binary(self, query, target, *args, **kwargs):
        pass

    @abstractmethod
    def similarity_gradient(self, query, target, *args, **kwargs):
        pass


class SkigramSimilarityModel(SimilarityModel):

    """
    TODO: this is a stub, to showcase the idea of a similarity model
    and how it can be implemented in different ways
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.similarity_threshold = kwargs.get("similarity_threshold", 0.5)
        return

    def similarity_binary(self, query, target, *args, **kwargs) -> bool:
        """
        We can binarize the similarity by taking the threshold over
        the distance in the latent space
        """
        similarity_score = self.similarity_gradient(query, target, *args, **kwargs)
        return similarity_score > self.similarity_threshold

    def similarity_gradient(self, query, target, *args, **kwargs) -> float:
        """
        We return the distance in the latent space
        """
        # TODO: replace this with the actual distance
        from random import random
        return random()


class GPT3SimilarityModel(SimilarityModel):

    API_URL = 'https://api.openai.com/v1/completions'
    MODEL = "text-davinci-002"
    TEMPERATURE = 0
    SIMILARITY_PROMPT = '''
        Imagine you are shopping for fashion products in a fashion store.
        Your best friend tells you to buy something as close as possible to this item:

        {}.

        The shopping assistant proposes the following alternative:

        {}.

        Is this second product similar enough to the one suggested by your friend? Provide a yes/no answer.
    '''

    """
    TODO: this is a stub, to showcase the idea of a similarity model
    and how it can be implemented in different ways
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # get the key from kwargs or fall back on envs
        self.api_key = kwargs.get("api_key", os.environ["OPENAI_API_KEY"])
        # you can override the model and temperature
        self.MODEL = kwargs.get("model", self.MODEL)
        self.TEMPERATURE = kwargs.get("temperature", self.TEMPERATURE)
        self.SIMILARITY_PROMPT = kwargs.get("similarity_prompt", self.SIMILARITY_PROMPT)
        return

    def similarity_binary(self, query, target, *args, **kwargs) -> bool:
        import requests
        # serialize the query and target
        query_str = ''
        for k, v in query.items():
            query_str += '{}: {} | '.format(k.strip(), v.replace('\n', ' ').strip())
        target_str = ''
        for k, v in target.items():
            target_str += '{}: {} | '.format(k.strip(), v.replace('\n', ' ').strip())
        final_prompt = self.SIMILARITY_PROMPT.format(query_str, target_str).strip()
        data =  {
                "model": self.MODEL,
                "prompt": final_prompt,
                "temperature": self.TEMPERATURE,
                "max_tokens": 10
                }
        headers = {
            'content-type': 'application/json',
            "Authorization": "Bearer {}".format(self.api_key)
            }
        r = requests.post(self.API_URL, data=json.dumps(data), headers=headers)
        # NOTE: we break if API call fails, alternative behavior are possible of course
        if r.status_code != 200:
            raise Exception("Error in GPT3 API call: {}".format(r.text))

        completion = json.loads(r.text)['choices'][0]['text']
        if kwargs.get("verbose", False):
            print("Query: {}".format(query_str))
            print("Target: {}".format(target_str))
            print("Prompt: {}".format(final_prompt))
            print("Completion: {}".format(completion))
        # if the first word is Yes, we return True
        first_word = completion.strip().split(" ")[0].lower()

        return first_word == "yes"

    def similarity_gradient(self, query, target, *args, **kwargs) -> float:
        raise Exception("No gradient is available for GPT3")


"""

### METADATA STORE SECTION ###

"""


class METADATA_STORE(Enum):
    LOCAL = 1
    S3 = 2


class MetaStore(ABC):

    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def write_file(self, path, data, is_json=False):
        pass


def metadata_store_factory(label) -> MetaStore:
    if label == METADATA_STORE.S3:
        return S3MetaStore
    else:
        return LocalMetaStore


class LocalMetaStore(MetaStore):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        return

    def write_file(self, path, data, is_json=False):
        if is_json:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        else:
            with open(path, "w") as f:
                f.write(data)

        return


class S3MetaStore(MetaStore):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        return

    def write_file(self, path, data, is_json=False):
        """
        We use s3fs to write to s3 - note: credentials are the default one
        locally stored in ~/.aws/credentials

        https://s3fs.readthedocs.io/en/latest/
        """
        import s3fs

        s3 = s3fs.S3FileSystem(anon=False)
        if is_json:
            with s3.open(path, 'wb') as f:
                f.write(json.dumps(data).encode('utf-8'))
        else:
            with s3.open(path, 'wb') as f:
                f.write(data)

        return


"""

### LOGGING SECTION ###

"""

class LOGGER(Enum):
    LOCAL = 1
    COMET = 2
    NEPTUNE = 3


class RecLogger(ABC):

    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def write(self, label, value):
        pass

    @abstractmethod
    def save_plot(self, name, fig, *args, **kwargs):
        pass


def logger_factory(label) -> RecLogger:
    if label == LOGGER.COMET:
        return CometLogger
    elif label == LOGGER.NEPTUNE:
        return NeptuneLogger
    else:
        return LocalLogger


class LocalLogger(RecLogger):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        return

    def write(self, label, value):
        from rich import print
        print(f"[italic red]{label}[/italic red]:{value}")

        return

    def save_plot(self, name, fig, *args, **kwargs):
        pass


class NeptuneLogger(RecLogger):

    def __init__(self, *args, **kwargs):
        """

        In order of priority, use first the kwargs, then the env variables

        """
        super().__init__(*args, **kwargs)
        import neptune

        api_key = kwargs.get("NEPTUNE_KEY", os.environ["NEPTUNE_KEY"])
        project_name = kwargs.get("NEPTUNE_PROJECT_NAME", os.environ["NEPTUNE_PROJECT_NAME"])

        self.experiment = neptune.init_run(
            project=project_name,
            api_token=api_key,
        )

        return

    def write(self, label, value):
        if isinstance(value, float):
            self.experiment[label] = value
        return

    def save_plot(self, name, fig, *args, **kwargs):
        import tempfile
        with tempfile.NamedTemporaryFile() as temp:
            file_name = temp.name + ".png"
            fig.savefig(file_name)
            self.experiment[name].upload(file_name)



class CometLogger(RecLogger):

    def __init__(self, *args, **kwargs):
        """

        In order of priority, use first the kwargs, then the env variables

        """
        super().__init__(*args, **kwargs)
        from comet_ml import Experiment

        api_key = kwargs.get("COMET_KEY", os.environ["COMET_KEY"])
        project_name = kwargs.get("COMET_PROJECT_NAME", os.environ["COMET_PROJECT_NAME"])
        workspace = kwargs.get("COMET_WORKSPACE", os.environ["COMET_WORKSPACE"])

        # set up the experiment
        self.experiment = Experiment(
            api_key=api_key,
            project_name=project_name,
            workspace=workspace,
        )

        return

    def write(self, label, value):
        if isinstance(value, float):
            self.experiment.log_metric(label, value)
        return

    def save_plot(self, name, fig, *args, **kwargs):
        import tempfile
        with tempfile.NamedTemporaryFile() as temp:
            file_name = temp.name + ".png"
            fig.savefig(file_name)
            self.experiment.log_image(file_name, name=name)


"""

### RECLIST SECTION ###

"""

def rec_test(test_type: str, display_type: CHART_TYPE = None):
    """
    Rec test decorator
    """

    def decorator(f):
        @wraps(f)
        def w(*args, **kwargs):
            return f(*args, **kwargs)

        # add attributes to f
        w.is_test = True
        w.test_type = test_type
        w.display_type = display_type
        try:
            w.test_desc = f.__doc__.lstrip().rstrip()
        except:
            w.test_desc = ""
        try:
            # python 3
            w.name = w.__name__
        except:
            # python 2
            w.name = w.__func__.func_name
        return w

    return decorator


class RecList(ABC):

    # this is the target metadata folder
    # it can be overwritten by the user
    # if an env variable is set
    META_DATA_FOLDER = os.environ.get("RECLIST_META_DATA_FOLDER", ".reclist")

    def __init__(
            self,
            model_name: str,
            logger: LOGGER = LOGGER.LOCAL,
            metadata_store: METADATA_STORE = METADATA_STORE.LOCAL,
            **kwargs,
            ):
        """
        :param model:
        :param dataset:
        """

        self.name = self.__class__.__name__
        self.model_name = model_name
        self._rec_tests = self.get_tests()
        self._test_results = []
        self.logger = logger
        self.logger_service = logger_factory(logger)(**kwargs)
        # if s3 is used, we need to specify the bucket
        self.metadata_bucket = kwargs["bucket"] if "bucket" in kwargs else None
        assert self.metadata_bucket is not None if metadata_store == METADATA_STORE.S3 else True, "If using S3, you need to specify the bucket"
        self.metadata_store_service = metadata_store_factory(metadata_store)(**kwargs)
        self.metadata_store = metadata_store

        return

    def get_tests(self):
        """
        Helper to extract methods decorated with rec_test
        """

        nodes = {}
        for _ in self.__dir__():
            if not hasattr(self, _):
                continue
            func = getattr(self, _)
            if hasattr(func, "is_test"):
                nodes[func.name] = func

        return nodes

    def create_data_store(self):
        """
        Each reclist run stores artifacts in

        METADATA_FOLDER/ReclistName/ModelName/RunEpochTimeMs
        """
        run_epoch_time_ms = round(time.time() * 1000)
        # specify a bucket as the root of the datastore if using s3
        bucket = self.metadata_bucket if self.metadata_store == METADATA_STORE.S3 else ''
        # create datastore path
        report_path = os.path.join(
            bucket,
            self.META_DATA_FOLDER,
            self.name,
            self.model_name,
            str(run_epoch_time_ms),
        )
        # create subfolders in the local file system if needed
        folders = ["artifacts", "results", "plots"]
        if self.metadata_store == METADATA_STORE.LOCAL:
            for folder in folders:
                Path(os.path.join(report_path, folder)).mkdir(
                    parents=True, exist_ok=True
                )

        return report_path

    def _display_rich_table(self, table_name: str, results: list):
        from rich.console import Console
        from rich.table import Table
        # build the rich table
        table = Table(title=table_name)
        table.add_column("Type", justify="right", style="cyan", no_wrap=True)
        table.add_column("Description ", style="magenta", no_wrap=False)
        table.add_column("Result", justify="right", style="green")
        for result in results:
            # rich needs strings to display
            printable_result = None
            if isinstance(result['result'], float):
                printable_result = str(round(result['result'], 4))
            elif isinstance(result['result'], dict):
                printable_result = json.dumps(result['result'], indent=4)
            elif isinstance(result['result'], list):
                printable_result = json.dumps(
                    result['result'][:3] + ["..."],
                    indent=4
                )
            else:
                printable_result = str(result['result'])
            table.add_row(
                result['name'],
                result['description'],
                printable_result
                )
        # print out the table
        console = Console()
        console.print(table)

        return

    def __call__(self, verbose=True, *args, **kwargs):
        from rich.progress import track

        self.meta_store_path = self.create_data_store()
        # iterate through tests
        for test_func_name, test in track(self._rec_tests.items(), description="Running RecTests"):
            test_result = test(*args, **kwargs)
            # we could store the results in the test function itself
            # test.__func__.test_result = test_result
            self._test_results.append(
                {
                    "name": test.test_type,
                    "description": test.test_desc,
                    "result": test_result,
                    "display_type": str(test.display_type),
                }
            )
            self.logger_service.write(test.test_type, test_result)
        # finally, display all results in a table
        self._display_rich_table(self.name, self._test_results)
        # at the end, dump results to json and generate plots
        test_2_fig = self._generate_report_and_plot(self._test_results, self.meta_store_path)
        for test, fig in test_2_fig.items():
            self.logger_service.save_plot(name=test, fig=fig)

        return

    def _generate_report_and_plot(self, test_results: list, meta_store_path: str):
        """
        Store a copy of the results into a file in the metadata store

        TODO: decide what to do with artifacts
        """
        # dump results to json
        report_file_name = self._dump_results_to_json(test_results, meta_store_path)
        # generate and save plots if applicable
        test_2_fig = self._generate_plots(test_results)
        for test_name, fig in test_2_fig.items():
            if self.metadata_store == METADATA_STORE.LOCAL:
                # TODO: decide if we want to save the plot in S3 or not
                fig.savefig(os.path.join(meta_store_path, "plots", "{}.png".format(test_name)))
        # TODO: decide how store artifacts / if / where
        # self.store_artifacts(report_path)
        return test_2_fig

    def _generate_plots(self, test_results: list):
        test_2_fig = {}
        for test_result in test_results:
            display_type = test_result['display_type']
            fig = None
            if display_type == str(CHART_TYPE.SCALAR):
                # TODO: decide how to plot scalars
                pass
            elif display_type == str(CHART_TYPE.BARS):
                fig = self._bar_chart(test_result)
            elif display_type == str(CHART_TYPE.BINS):
                fig = self._bin_chart(test_result)
            # append fig to the mapping
            if fig is not None:
                test_2_fig[test_result['name']] = fig

        return test_2_fig

    def _bin_chart(self, test_result: dict):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_title(test_result['name'])
        data = test_result['result']
        assert isinstance(data, list), "data must be a list"
        ax.hist(data, color='lightgreen', ec='black')

        return fig

    def _bar_chart(self, test_result: dict):
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_title(test_result['name'])
        data = test_result['result'].keys()
        ax.bar(data, [test_result['result'][_] for _ in data])

        return fig


    def _dump_results_to_json(self, test_results: list, report_path: str):
        report = {
            "metadata": {
                "model_name": self.model_name,
                "reclist": self.name,
                "tests": list(self._rec_tests.keys()),
            },
            "data": test_results,
        }
        report_file_name = os.path.join(report_path, "results", "report.json")
        self.metadata_store_service.write_file(
            report_file_name,
            report,
            is_json=True
        )

        return report_file_name

    @property
    def rec_tests(self):
        return self._rec_tests


class FreeSessionRecList(RecList):

    def __init__(
        self,
        dataset,
        metadata,
        predictions,
        model_name,
        logger: LOGGER,
        metadata_store: METADATA_STORE,
        **kwargs
    ):
        super().__init__(
            model_name,
            logger,
            metadata_store,
            **kwargs
        )
        self.dataset = dataset
        self.metadata = metadata
        self.predictions = predictions
        self.similarity_model = kwargs.get("similarity_model", None)

        return

    @rec_test(test_type="LessWrong", display_type=CHART_TYPE.BINS)
    def less_wrong(self):
        truths = self.dataset
        predictions = self.predictions
        model_misses = [(t, p) for t, p in zip(truths, predictions) if t != p]
        similarity_scores = [
            self.similarity_model.similarity_gradient(t, p) for t, p in model_misses
        ]

        return similarity_scores

    @rec_test(test_type="SlicedAccuracy", display_type=CHART_TYPE.SCALAR)
    def sliced_accuracy(self):
        """
        Compute the accuracy by slice
        """
        from metrics.standard_metrics import accuracy_per_slice

        return accuracy_per_slice(
            self.dataset, self.predictions, self.metadata["categories"]
        )

    @rec_test(test_type="Accuracy", display_type=CHART_TYPE.SCALAR)
    def accuracy(self):
        """
        Compute the accuracy
        """
        from sklearn.metrics import accuracy_score

        return accuracy_score(self.dataset, self.predictions)

    @rec_test(test_type="AccuracyByCountry", display_type=CHART_TYPE.BARS)
    def accuracy_by_country(self):
        """
        Compute the accuracy by country
        """
        # TODO: note that is a static test, used to showcase the bin display
        from random import randint
        return { "US": randint(0, 100), "CA": randint(0, 100), "FR": randint(0, 100) }


class DFSessionRecList(RecList):

    def __init__(
        self,
        dataset,
        predictions,
        model_name,
        logger: LOGGER,
        metadata_store: METADATA_STORE,
        **kwargs
    ):
        super().__init__(
            model_name,
            logger,
            metadata_store,
            **kwargs
        )
        self.dataset = dataset
        self._y_preds = predictions
        self._y_test = kwargs.get("y_test", None)
        self.similarity_model = kwargs.get("similarity_model", None)

        return

    @rec_test('HIT_RATE')
    def hit_rate_at_100(self):
        hr = self.hit_rate_at_k(self._y_preds, self._y_test, k=100)
        return hr

    def hit_rate_at_k(self, y_pred: pd.DataFrame, y_test: pd.DataFrame, k: int):
        """
        N = number test cases
        M = number ground truth per test case
        """
        hits = self.hits_at_k(y_pred, y_test, k)  # N x M x k
        hits = hits.max(axis=1)  # N x k
        return hits.max(axis=1).mean()  # 1

    def hits_at_k(self, y_pred: pd.DataFrame, y_test: pd.DataFrame, k: int):
        """
        N = number test cases
        M = number ground truth per test case
        """
        y_test_mask = y_test.values != -1  # N x M

        y_pred_mask = y_pred.values[:, :k] != -1  # N x k

        y_test = y_test.values[:, :, None]  # N x M x 1
        y_pred = y_pred.values[:, None, :k]  # N x 1 x k

        hits = y_test == y_pred  # N x M x k
        hits = hits * y_test_mask[:, :, None]  # N x M x k
        hits = hits * y_pred_mask[:, None, :]  # N x M x k

        return hits

"""

### RUNNING SECTION ###

"""

try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    print("Dotenv not loaded: if you need ENV variables, make sure you export them manually")


class myModel:

    def __init__(self, n):
        self.n = n

    def predict(self):
        """
        Do something
        """
        from random import randint
        return [randint(0, 1) for _ in range(self.n)]


# create a dataset randomly
from random import randint, choice
n = 10000
apo_model = myModel(n)
dataset = [randint(0, 1) for _ in range(n)]
metadata = {"categories": [choice(["cat", "dog", "capybara"]) for _ in range(n)]}
predictions = apo_model.predict()
my_sim_model = SkigramSimilarityModel()
assert len(dataset) == len(predictions), "dataset, predictions must have the same length"


# initialize with everything
cd = FreeSessionRecList(
    dataset=dataset,
    metadata=metadata,
    predictions=predictions,
    model_name="myRandomModel",
    logger=LOGGER.COMET,
    metadata_store= METADATA_STORE.LOCAL,
    similarity_model=my_sim_model,
    bucket=os.environ["S3_BUCKET"],
    COMET_KEY=os.environ["COMET_KEY"],
    COMET_PROJECT_NAME=os.environ["COMET_PROJECT_NAME"],
    COMET_WORKSPACE=os.environ["COMET_WORKSPACE"],
)

# run reclist
cd(verbose=True)

# test the similarity model with open ai :clownface:
#sim_model = GPT3SimilarityModel(api_key=os.environ["OPENAI_API_KEY"])
#p1 = {
#    "name": "logo-print cotton cap",
#    "brand": 'Palm Angels',
#    "description": '''
#    Known for a laid-back aesthetic, Palm Angels knows how to portray its Californian inspiration. This classic cap carries the brand's logo printed on the front, adding a touch of recognition to a relaxed look.
#    '''
#}
#p2 = {
#    "name": "monogram badge cap",
#    "brand": 'Balmain',
#    "description": '''
#    Blue cotton monogram badge cap from Balmain featuring logo patch to the front, mesh detailing, fabric-covered button at the crown and adjustable fit.
#    '''
#}
#similarity_judgement = sim_model.similarity_binary(p1, p2, verbose=False)
#print("P1 {} and P2 {} are similar: {}".format(p1["name"], p2["name"], similarity_judgement))


class MySuperModel():

    def __init__(self, items: pd.DataFrame, top_k: int=10, **kwargs):
        self.items = items
        self.top_k = top_k
        print("Received additional arguments: {}".format(kwargs))
        return

    def predict(self, user_ids: pd.DataFrame) -> pd.DataFrame:
        k = self.top_k
        num_users = len(user_ids)
        pred = self.items.sample(n=k*num_users, replace=True).index.values
        pred = pred.reshape(num_users, k)
        pred = np.concatenate((user_ids[['user_id']].values, pred), axis=1)
        return pd.DataFrame(pred, columns=['user_id', *[str(i) for i in range(k)]]).set_index('user_id')


print("\n\n ======> Loading dataset. \n\n")
df_events = pd.read_csv('evalrs_dataset_KDD23/evalrs_events.csv', index_col=0, dtype='int32')
df_tracks = pd.read_csv('evalrs_dataset_KDD23/evalrs_tracks.csv',
                                dtype={
                                    'track_id': 'int32',
                                    'artist_id': 'int32'
                                }).set_index('track_id')

df_users = pd.read_csv('evalrs_dataset_KDD23/evalrs_users.csv',
                            dtype={
                                'user_id': 'int32',
                                'playcount': 'int32',
                                'country_id': 'int32',
                                'timestamp': 'int32',
                                'age': 'int32',
                            })

my_df_model = MySuperModel(df_tracks, top_k=10)
df_predictions = my_df_model.predict(df_users)
# build a mock dataset for the golden standard
all_tracks = df_tracks.index.values
from random import choice
df_dataset = pd.DataFrame(
    {
        'track_id': [choice(all_tracks) for _ in range(len(df_predictions))]
    }
)

# initialize with everything
cdf = DFSessionRecList(
    dataset=df_events,
    model_name="myDataFrameRandomModel",
    predictions=df_predictions,
    # I can specify the gold standard here, or doing it in the init of course
    y_test=df_dataset,
    logger=LOGGER.NEPTUNE,
    metadata_store= METADATA_STORE.LOCAL,
    similarity_model=my_sim_model,
    bucket=os.environ["S3_BUCKET"],
    NEPTUNE_KEY=os.environ["NEPTUNE_KEY"],
    NEPTUNE_PROJECT_NAME=os.environ["NEPTUNE_PROJECT_NAME"],
)

# run reclist
cdf(verbose=True)
