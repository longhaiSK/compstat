source("renv/activate.R")
## python chunks (reticulate) use the virtual environment in ~/Github/bin
py <- path.expand("~/Github/bin/.venv/bin/python")
if (file.exists(py)) {
  Sys.setenv(RETICULATE_PYTHON = py)
} else if (!nzchar(Sys.getenv("RETICULATE_PYTHON"))) {
  warning("Python environment not found at ", py, ": python chunks (TensorFlow example) ",
          "need RETICULATE_PYTHON to point to a Python with numpy, tensorflow and matplotlib.",
          call. = FALSE)
}
