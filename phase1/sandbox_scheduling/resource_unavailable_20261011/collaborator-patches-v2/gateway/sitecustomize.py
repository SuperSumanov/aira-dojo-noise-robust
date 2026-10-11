import os,sys
if os.path.basename(sys.argv[0])=='jupyter-kernelgateway':
    import kernel_shutdown_guard
