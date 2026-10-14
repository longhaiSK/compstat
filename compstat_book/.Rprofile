source("renv/activate.R")
## python chunks (reticulate) use the virtual environment in ~/Github/bin
py <- path.expand("~/Github/bin/.venv/bin/python")
if (file.exists(py)) {
  Sys.setenv(RETICULATE_PYTHON = py)
} else {
  warning("Python environment not found at ", py, ". Python chunks (the TensorFlow example) ",
          "will use RETICULATE_PYTHON = '", Sys.getenv("RETICULATE_PYTHON"), "', which needs ",
          "numpy, tensorflow and matplotlib.", call. = FALSE)
}
