# Primary mortality analysis v1 wrapper
# The local Codex runtime used for this run did not provide Rscript.
# This wrapper records the requested R entrypoint and delegates to the executed Python implementation.
python <- Sys.which('python')
if (python == '') stop('Python executable not found on PATH. Run run_primary_mortality_v1.py with the Codex bundled Python.')
script <- 'E:/Codex/SCI/projects/mental_delirium_longterm/scripts/analysis/run_primary_mortality_v1.py'
status <- system2(python, script)
quit(status = status)
