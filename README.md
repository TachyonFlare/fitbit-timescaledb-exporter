# fitbit-timescaledb-exporter
Exporter for piping metrics from fitbit to timescale-db

![Image](./screenshots/Dashboard.png?raw=true)

Has two components
- `Downloader.py` - downloads your fitbit data using personal access token.
- `Sender.py` - parses the locally downloaded fitbit data and stores it in timescale-db

**How to run**
- Create `config.json`, you can use `sample_config.json` as reference and update the fields as required. Currently, `sample_config.json` has all the fields that can be configured and config parameters are self explanatory.
- Create [pipenv](https://pipenv.pypa.io/en/latest/) for the python scripts using the pipfile.
- Run `Downloader.py` which fetches user data from fitbit. This can run for pretty long depending on the start date set in the config file and rate limits imposed by fitbit.
- Run `Sender.py` to parse the data and push to timescale-db

**Tasks**

- [x] MVP for `downloader.py`
- [x] MVP for `sender.py`
- [ ] Add `cron.sh` for adding the scripts to local cron.
- [ ] Add `docker-compose.yml` for ease of deployment.
    - [x] Timescale-db
    - [x] Grafana
    - [ ] Downloader
    - [ ] Sender
    - [ ] Jenkins
- [ ] compression policies for timescale
- [ ] summary tables as materialized views
- [ ] code cleanup
    - [ ] parse all activity info from fitbit public api and expand the activity enums.
    - [ ] move functions common across sender and downloader to a single file.
    - [ ] reduce code duplication in hypertable creation for all models.
    - [ ] move constants to config or a seperate file (?) 

