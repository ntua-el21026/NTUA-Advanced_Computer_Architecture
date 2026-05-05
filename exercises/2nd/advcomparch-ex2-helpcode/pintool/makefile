# If the tool is built out of the kit, PIN_ROOT must be specified in the make invocation and point to the kit root.
PIN_ROOT ?= /home/peppasmich/NTUA-Advanced_Computer_Architecture/exercises/1st/pin-external-4.2-99776-g21d818fa2-gcc-linux

CONFIG_ROOT := $(PIN_ROOT)/source/tools/Config
include $(CONFIG_ROOT)/makefile.config
include makefile.rules
include $(TOOLS_ROOT)/Config/makefile.default.rules

override export PIN_WRAPPER_GCC := /usr/bin/gcc
