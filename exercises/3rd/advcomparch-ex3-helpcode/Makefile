CC := gcc

BIN_DIR ?= bin
SNIPER_BASE_DIR ?= /root/sniper
SNIPER_INCLUDE_DIR := $(SNIPER_BASE_DIR)/include

CPPFLAGS ?=
CFLAGS ?= -Wall -O0
CFLAGS += -Wno-unused-variable
LDFLAGS ?=
LDLIBS ?= -pthread

SOURCE := locks_scalability.c
HEADERS := lock.h

IMPLEMENTATIONS := tas_cas tas_ts ttas_cas ttas_ts mutex

LOCK_FLAG_tas_cas := TAS_CAS
LOCK_FLAG_tas_ts := TAS_TS
LOCK_FLAG_ttas_cas := TTAS_CAS
LOCK_FLAG_ttas_ts := TTAS_TS
LOCK_FLAG_mutex := MUTEX

REAL_BINARIES := $(addprefix $(BIN_DIR)/locks_,$(addsuffix _real,$(IMPLEMENTATIONS)))
SNIPER_BINARIES := $(addprefix $(BIN_DIR)/locks_,$(addsuffix _sniper,$(IMPLEMENTATIONS)))

TEST_THREADS ?= 4
TEST_ITERATIONS ?= 10000
TEST_GRAIN ?= 10

.PHONY: all real sniper check-real check-sniper-config clean help

all: real

real: $(REAL_BINARIES)

sniper: check-sniper-config $(SNIPER_BINARIES)

$(BIN_DIR):
	mkdir -p $@

define REAL_BINARY_template
$(BIN_DIR)/locks_$(1)_real: $(SOURCE) $(HEADERS) | $(BIN_DIR)
	$(CC) $(CPPFLAGS) $(CFLAGS) -DREAL -D$(LOCK_FLAG_$(1)) \
		$(SOURCE) $(LDFLAGS) $(LDLIBS) -o $$@
endef

define SNIPER_BINARY_template
$(BIN_DIR)/locks_$(1)_sniper: $(SOURCE) $(HEADERS) | $(BIN_DIR) check-sniper-config
	$(CC) $(CPPFLAGS) $(CFLAGS) -DSNIPER -D$(LOCK_FLAG_$(1)) \
		-I$(SNIPER_INCLUDE_DIR) $(SOURCE) $(LDFLAGS) $(HOOKS_LDFLAGS) \
		$(LDLIBS) -o $$@
endef

$(foreach implementation,$(IMPLEMENTATIONS),\
	$(eval $(call REAL_BINARY_template,$(implementation))))
$(foreach implementation,$(IMPLEMENTATIONS),\
	$(eval $(call SNIPER_BINARY_template,$(implementation))))

check-real: real
	@set -e; \
	for binary in $(REAL_BINARIES); do \
		echo "CHECK $$binary"; \
		timeout 30s "$$binary" \
			$(TEST_THREADS) $(TEST_ITERATIONS) $(TEST_GRAIN); \
	done

check-sniper-config:
	@test -f "$(SNIPER_INCLUDE_DIR)/sim_api.h" || { \
		echo "Missing $(SNIPER_INCLUDE_DIR)/sim_api.h" >&2; \
		echo "Set SNIPER_BASE_DIR to the Sniper installation directory." >&2; \
		exit 1; \
	}

# Backwards-compatible one-off build:
#   make locks IMPLFLAG=-DREAL LFLAG=-DTAS_CAS
IMPLFLAG ?= -DSNIPER
LFLAG ?= -DMUTEX
LEGACY_SNIPER_CPPFLAGS := $(if $(findstring -DSNIPER,$(IMPLFLAG)),-I$(SNIPER_INCLUDE_DIR))

locks: $(SOURCE) $(HEADERS)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(IMPLFLAG) $(LFLAG) \
		$(LEGACY_SNIPER_CPPFLAGS) $(SOURCE) $(LDFLAGS) $(HOOKS_LDFLAGS) \
		$(LDLIBS) -o $@

clean:
	rm -rf $(BIN_DIR) locks

help:
	@echo "make real          Build all five real-machine binaries"
	@echo "make sniper        Build all five Sniper binaries"
	@echo "make check-real     Build and validate all real-machine binaries"
	@echo "make clean          Remove generated binaries"
	@echo
	@echo "Sniper example:"
	@echo "  make sniper SNIPER_BASE_DIR=/root/sniper"
	@echo
	@echo "Validation overrides:"
	@echo "  make check-real TEST_THREADS=8 TEST_ITERATIONS=100000 TEST_GRAIN=1"
