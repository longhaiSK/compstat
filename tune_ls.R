## Compares SGD + Adam / momentum / line search at their best fixed learning rate with the
## independent-batch line search versions (shinylive_apps/app_sgd.qmd), by test loss.
## Run from the repository root:  Rscript tune_ls.R
q <- readLines("shinylive_apps/app_sgd.qmd")
a <- grep("^```\\{shinylive-r\\}", q)[1]; b <- grep("^ALGS <- c\\(", q)[1]
eval(parse(text = q[(a + 1):(b - 1)]))      # model, data, line_search and run_alg of the app
LR <- c(1e-5,3e-5,1e-4,3e-4,1e-3,3e-3,.01,.03,.1,.3,1)
te <- make_data(2000, 0.3, 999)
one <- function(J, seed, n=200, ep=100) {
  D <- make_data(n, 0.3, seed); th0 <- rand_start(seed, J)
  tl <- function(a, lr) { r <- run_alg(a, th0, D$x, D$y, ep, lr=lr, mom=0.9, m=20)
    c(train=tail(r$L,1), test=loss_fun(r$P[nrow(r$P),], te$x, te$y)) }
  res <- list()
  for (a in c("adam","mom","sgdls")) {
    M <- t(sapply(LR, function(l) tl(a, l))); rownames(M) <- LR
    res[[a]] <- c(best_lr=LR[which.min(M[,"test"])], best=min(M[,"test"]), worst=max(M[,"test"][is.finite(M[,"test"])]))
  }
  for (a in c("adamls","momls","sgdls2")) {
    M <- t(sapply(LR[c(3,6,8,10)], function(l) tl(a, l)))
    res[[a]] <- c(best_lr=NA, best=min(M[,"test"]), worst=max(M[,"test"]))
  }
  res
}
for (J in c(4, 20)) for (seed in 1:3) {
  r <- one(J, seed); cat("J",J,"seed",seed,"\n")
  for (a in names(r)) cat(sprintf("  %-7s best test %.4f  (best lr %s; worst over grid %.3f)\n", a, r[[a]]["best"], r[[a]]["best_lr"], r[[a]]["worst"]))
}
