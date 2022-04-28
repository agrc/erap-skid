# Emergency Rental Assistance Payment Skid

A Google Cloud Function that updates the ERAP AGOL data from exports uploaded to FTP.

## Setup Local Dev Environment

1. Create new environment
   - `conda create --name erapskid python=3.7`
   - `conda activate erapskid`
1. Install local GCF framework
   - `pip install functions-framework`
1. Install in dev mode
   - `cd c:\path\to\repo`
   - `pip install -e .[tests]`

## Run Locally

See [Google's Documentation](https://cloud.google.com/functions/docs/running/function-frameworks) for detailed info.

1. Navigate to the project folder within `src`:
   - `cd c:\path\to\repo\src\erap`
1. Start the local functions framework server. This will attempt to load the function and prepare it to be run, but doesn't actually call it.
   - `functions-framework --target=main --signature-type=event`
1. Open a bash shell (git-bash if you installed git for Windows) and run the pubsub.sh script to call the function itself with an HTTP request via curl:
   - `/c/path/to/repo/pubsub.sh`

The bash shell will just return an HTTP response. The terminal you started functions-framework should show anything you send to stdout/stderr (print() statements, logging to console, etc).

If you make changes to your code, you need to kill (ctrl-c) and restart functions-framework to load the changes.

## Setup Cloud Dev/Prod Environments

ERAP runs as a Cloud Function triggered by Cloud Scheduler sending a notification to a pub/sub topic on a regular schedule (currently Monday at 9:00 a.m.)

Work with the GCP maestros to set up a Google project via terraform. ERAP uses the following GCP resources:

- Cloud Function (obviously)
- Cloud Storage (writes the data file and log file for mid-term retention)
  - Should have a 90-day retention policy set
- Cloud Scheduler (send a notification to a pub/sub topic)
- Cloud Pub/Sub (create a topic that links Scheduler and the cloud function)
- Secrets Manager
  - A `secrets.json` with the requisite login info
  - A `known_hosts` file with the sftp server's public key

## Setup GitHub CI Pipeline

ERAP uses a GitHub action to deploy the function, pub/sub topic, and scheduler action to the GCP project. It uses the following GitHub secrets to do this:

- Identity provider
- GCP service account email
- Project ID
- Storage Bucket ID

The ERAP cloud function needs 512 MB of RAM to run successfully. The source dir should point to `src/erap`. A cloud function just runs the specified function in the `main.py` in the source dir; it doesn't pip install the function itself.

## Developing the ERAP Skid

As just noted, Cloud Functions just look for a specified function with a `main.py` file. There can be other modules or sub-packages alongside `main.py`, but it doesn't look like the normal `from . import <module>.py` relative import works in the cloud function. To get around this while still providing something that is pip-installable locally for integrated VS Code tests, I've done the following:

```python
try:
    from . import config, version
except ImportError:
    import config
    import version
```

Python Cloud Functions can be triggered two different ways: by simple HTTP request or by publishing to a pub/sub topic (referred to as a "background function" or an "event" trigger). ERAP is a background function, hence the more complicated calling method in the Run Locally section above.

The entry function in `main.py` should accept two arguments. ERAP just ignores them, but they allow you to access the triggering event and its context. See the [Google docs](https://cloud.google.com/functions/docs/writing/background#cloud-pubsub-example) for an example entry function.

The entry function then calls other functions in the local modules and installed dependencies. Dependencies must be pip-installable from PyPi and are specified in the `requirements.txt` file in the `src/erap` directory. Ergo, `arcgis` is in, but `arcpy` is out.
