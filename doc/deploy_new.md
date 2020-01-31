# Deploying from scratch

These are the steps needed to deploy a new instance of the app.  The first time you run the app locally, you'll need to follow these steps.  In general, you don't need to follow these steps to deploy code changes to prod.

These steps supplement, but do not replace, the [App Engine documentation](https://cloud.google.com/appengine/docs/standard/python/quickstart).  The steps listed here are specific to cubingusa.org.

1. Run `./dev_app.sh` and `./run_sass.sh`.  Both of these will run 
1. Visit [http://localhost:8081/app_settings] and follow the steps there to configure various API keys.  You'll need to set a session secret key and WCA OAuth; the remaining settings are optional.
1. Sign in using [http://localhost:8080/login] with your WCA account.
1. Grant yourself global admin access by visiting [http://localhost:8081/assign_role/$YOUR_WCA_ID/GLOBAL_ADMIN].
1. Populate some basic data by visiting [http://localhost:8081/update_states].
1. Import the latest WCA export by visitng [http://localhost:8081/wca/get_export].  This will take about half an hour to run the first time; incremental updates are much faster.  The terminal running `dev_app.sh` will continue producing output until it's done.
1. Select championships by visiting [http://localhost:8080/admin/edit_championships].
1. Compute the list of champions by visiting [http://localhost:8081/post_import_mutations].  Normally this is run at the end of `/wca/get_export`.

These steps only need to be run once.  In the future, you only need to run the first step to start the local server.
