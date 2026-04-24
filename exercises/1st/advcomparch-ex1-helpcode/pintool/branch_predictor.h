#ifndef BRANCH_PREDICTOR_H
#define BRANCH_PREDICTOR_H

#include <sstream> // std::ostringstream
#include <cmath>   // pow()
#include <cstring> // memset()
#include <cassert> // assert()
#include <string>
#include <vector>

/**
 * A generic BranchPredictor base class.
 * All predictors can be subclasses with overloaded predict() and update()
 * methods.
 **/
class BranchPredictor
{
public:
    BranchPredictor() : correct_predictions(0), incorrect_predictions(0) {};
    ~BranchPredictor() {};

    virtual bool predict(ADDRINT ip, ADDRINT target) = 0;
    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) = 0;
    virtual string getName() = 0;

    UINT64 getNumCorrectPredictions() { return correct_predictions; }
    UINT64 getNumIncorrectPredictions() { return incorrect_predictions; }

    void resetCounters() { correct_predictions = incorrect_predictions = 0; };

protected:
    void updateCounters(bool predicted, bool actual) {
        if (predicted == actual)
            correct_predictions++;
        else
            incorrect_predictions++;
    };

private:
    UINT64 correct_predictions;
    UINT64 incorrect_predictions;
};

static unsigned int predictorCounterMax(unsigned int counter_bits) {
    return (1u << counter_bits) - 1u;
}

static bool predictorCounterTaken(unsigned int counter, unsigned int counter_bits) {
    return counter >= (1u << (counter_bits - 1));
}

static void predictorUpdateCounter(unsigned int &counter, unsigned int counter_max, bool actual) {
    if (actual) {
        if (counter < counter_max)
            counter++;
    } else {
        if (counter > 0)
            counter--;
    }
}

static unsigned int predictorPcIndex(ADDRINT ip, unsigned int entries) {
    return (ip >> 2) % entries;
}

class StaticAlwaysTakenPredictor : public BranchPredictor
{
public:
    StaticAlwaysTakenPredictor() : BranchPredictor() {}

    virtual bool predict(ADDRINT ip, ADDRINT target) {
        return true;
    }

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
        updateCounters(predicted, actual);
    }

    virtual string getName() {
        return "Static-AlwaysTaken";
    }
};

class StaticBTFNTPredictor : public BranchPredictor
{
public:
    StaticBTFNTPredictor() : BranchPredictor() {}

    virtual bool predict(ADDRINT ip, ADDRINT target) {
        return target < ip;
    }

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
        updateCounters(predicted, actual);
    }

    virtual string getName() {
        return "Static-BTFNT";
    }
};

class NbitPredictor : public BranchPredictor
{
public:
    NbitPredictor(unsigned index_bits_, unsigned cntr_bits_)
        : BranchPredictor(), index_bits(index_bits_), cntr_bits(cntr_bits_) {
        table_entries = 1 << index_bits;
        TABLE = new unsigned long long[table_entries];
        memset(TABLE, 0, table_entries * sizeof(*TABLE));
        
        COUNTER_MAX = (1 << cntr_bits) - 1;
    };
    ~NbitPredictor() { delete[] TABLE; };

    virtual bool predict(ADDRINT ip, ADDRINT target) {
        unsigned int ip_table_index = ip % table_entries;
        unsigned long long ip_table_value = TABLE[ip_table_index];
        unsigned long long prediction = ip_table_value >> (cntr_bits - 1);
        return (prediction != 0);
    };

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
        unsigned int ip_table_index = ip % table_entries;
        if (actual) {
            if (TABLE[ip_table_index] < COUNTER_MAX)
                TABLE[ip_table_index]++;
        } else {
            if (TABLE[ip_table_index] > 0)
                TABLE[ip_table_index]--;
        }
        
        updateCounters(predicted, actual);
    };

    virtual string getName() {
        std::ostringstream stream;
        stream << "Nbit-" << pow(2.0,double(index_bits)) / 1024.0 << "K-" << cntr_bits;
        return stream.str();
    }

private:
    unsigned int index_bits, cntr_bits;
    unsigned int COUNTER_MAX;
    
    /* Make this unsigned long long so as to support big numbers of cntr_bits. */
    unsigned long long *TABLE;
    unsigned int table_entries;
};

class LocalHistoryTwoLevelPredictor : public BranchPredictor
{
public:
    LocalHistoryTwoLevelPredictor(unsigned int bht_entries_, unsigned int history_bits_,
                                  unsigned int pht_entries_, unsigned int counter_bits_)
        : BranchPredictor(),
          bht_entries(bht_entries_),
          history_bits(history_bits_),
          pht_entries(pht_entries_),
          counter_bits(counter_bits_),
          history_mask((1u << history_bits_) - 1u),
          counter_max(predictorCounterMax(counter_bits_)),
          bht(bht_entries_, 0),
          pht(pht_entries_, 0) {
    }

    virtual bool predict(ADDRINT ip, ADDRINT target) {
        unsigned int bht_index = predictorPcIndex(ip, bht_entries);
        unsigned int pht_index = phtIndex(ip, bht[bht_index]);
        return predictorCounterTaken(pht[pht_index], counter_bits);
    }

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
        unsigned int bht_index = predictorPcIndex(ip, bht_entries);
        unsigned int old_history = bht[bht_index];
        unsigned int pht_index = phtIndex(ip, old_history);

        unsigned int counter = pht[pht_index];
        predictorUpdateCounter(counter, counter_max, actual);
        pht[pht_index] = counter;

        bht[bht_index] = ((old_history << 1) | (actual ? 1u : 0u)) & history_mask;
        updateCounters(predicted, actual);
    }

    virtual string getName() {
        std::ostringstream stream;
        stream << "Local-X" << bht_entries << "-Z" << history_bits
               << "-PHT" << (pht_entries / 1024) << "K-" << counter_bits;
        return stream.str();
    }

private:
    unsigned int phtIndex(ADDRINT ip, unsigned int history) {
        return (predictorPcIndex(ip, pht_entries) ^ history) % pht_entries;
    }

    unsigned int bht_entries;
    unsigned int history_bits;
    unsigned int pht_entries;
    unsigned int counter_bits;
    unsigned int history_mask;
    unsigned int counter_max;
    std::vector<unsigned int> bht;
    std::vector<unsigned int> pht;
};

class GlobalHistoryTwoLevelPredictor : public BranchPredictor
{
public:
    GlobalHistoryTwoLevelPredictor(unsigned int pht_entries_, unsigned int bhr_bits_,
                                   unsigned int counter_bits_)
        : BranchPredictor(),
          pht_entries(pht_entries_),
          bhr_bits(bhr_bits_),
          counter_bits(counter_bits_),
          history_mask((1u << bhr_bits_) - 1u),
          counter_max(predictorCounterMax(counter_bits_)),
          global_history(0),
          pht(pht_entries_, 0) {
    }

    virtual bool predict(ADDRINT ip, ADDRINT target) {
        unsigned int pht_index = phtIndex(ip);
        return predictorCounterTaken(pht[pht_index], counter_bits);
    }

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
        unsigned int pht_index = phtIndex(ip);
        unsigned int counter = pht[pht_index];
        predictorUpdateCounter(counter, counter_max, actual);
        pht[pht_index] = counter;

        global_history = ((global_history << 1) | (actual ? 1u : 0u)) & history_mask;
        updateCounters(predicted, actual);
    }

    virtual string getName() {
        std::ostringstream stream;
        stream << "Global-PHT" << (pht_entries / 1024) << "K-BHR"
               << bhr_bits << "-" << counter_bits;
        return stream.str();
    }

private:
    unsigned int phtIndex(ADDRINT ip) {
        return (predictorPcIndex(ip, pht_entries) ^ global_history) % pht_entries;
    }

    unsigned int pht_entries;
    unsigned int bhr_bits;
    unsigned int counter_bits;
    unsigned int history_mask;
    unsigned int counter_max;
    unsigned int global_history;
    std::vector<unsigned int> pht;
};

class Alpha21264Predictor : public BranchPredictor
{
public:
    Alpha21264Predictor()
        : BranchPredictor(),
          local_history_table(1024, 0),
          local_pht(1024, 0),
          global_pht(4096, 0),
          choice_pht(4096, 0),
          global_history(0) {
    }

    virtual bool predict(ADDRINT ip, ADDRINT target) {
        bool local_prediction = predictLocal(ip);
        bool global_prediction = predictGlobal(ip);
        return chooseGlobal(ip) ? global_prediction : local_prediction;
    }

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
        unsigned int local_history_index = predictorPcIndex(ip, 1024);
        unsigned int old_local_history = local_history_table[local_history_index];
        unsigned int local_pht_index = old_local_history % 1024;
        unsigned int global_pht_index = globalIndex(ip);
        unsigned int choice_index = global_pht_index;

        bool local_prediction = predictorCounterTaken(local_pht[local_pht_index], 3);
        bool global_prediction = predictorCounterTaken(global_pht[global_pht_index], 2);

        if (local_prediction != global_prediction) {
            unsigned int choice = choice_pht[choice_index];
            if (global_prediction == actual)
                predictorUpdateCounter(choice, 3, true);
            else if (local_prediction == actual)
                predictorUpdateCounter(choice, 3, false);
            choice_pht[choice_index] = choice;
        }

        unsigned int local_counter = local_pht[local_pht_index];
        predictorUpdateCounter(local_counter, 7, actual);
        local_pht[local_pht_index] = local_counter;

        unsigned int global_counter = global_pht[global_pht_index];
        predictorUpdateCounter(global_counter, 3, actual);
        global_pht[global_pht_index] = global_counter;

        local_history_table[local_history_index] =
            ((old_local_history << 1) | (actual ? 1u : 0u)) & 0x3ffu;
        global_history = ((global_history << 1) | (actual ? 1u : 0u)) & 0xfffu;

        updateCounters(predicted, actual);
    }

    virtual string getName() {
        return "Alpha21264";
    }

private:
    bool predictLocal(ADDRINT ip) {
        unsigned int local_history_index = predictorPcIndex(ip, 1024);
        unsigned int local_pht_index = local_history_table[local_history_index] % 1024;
        return predictorCounterTaken(local_pht[local_pht_index], 3);
    }

    bool predictGlobal(ADDRINT ip) {
        return predictorCounterTaken(global_pht[globalIndex(ip)], 2);
    }

    bool chooseGlobal(ADDRINT ip) {
        return predictorCounterTaken(choice_pht[globalIndex(ip)], 2);
    }

    unsigned int globalIndex(ADDRINT ip) {
        return (predictorPcIndex(ip, 4096) ^ global_history) % 4096;
    }

    std::vector<unsigned int> local_history_table;
    std::vector<unsigned int> local_pht;
    std::vector<unsigned int> global_pht;
    std::vector<unsigned int> choice_pht;
    unsigned int global_history;
};

class NairTwoBitFsmPredictor : public BranchPredictor
{
public:
    NairTwoBitFsmPredictor(unsigned index_bits_, const std::string &machine_, unsigned output_mask_)
        : BranchPredictor(), index_bits(index_bits_), machine(machine_), output_mask(output_mask_) {
        assert(machine.size() == 8);
        table_entries = 1 << index_bits;
        TABLE = new unsigned char[table_entries];
        memset(TABLE, 0, table_entries * sizeof(*TABLE));

        for (unsigned state = 0; state < 4; state++) {
            transitions[state][0] = decodeState(machine[2 * state]);
            transitions[state][1] = decodeState(machine[2 * state + 1]);
        }
    };

    ~NairTwoBitFsmPredictor() { delete[] TABLE; };

    virtual bool predict(ADDRINT ip, ADDRINT target) {
        unsigned int ip_table_index = ip % table_entries;
        unsigned int state = TABLE[ip_table_index];
        return predictsTaken(state);
    };

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
        unsigned int ip_table_index = ip % table_entries;
        unsigned int state = TABLE[ip_table_index];
        TABLE[ip_table_index] = transitions[state][actual ? 1 : 0];

        updateCounters(predicted, actual);
    };

    virtual string getName() {
        std::ostringstream stream;
        stream << "FSM-" << pow(2.0, double(index_bits)) / 1024.0 << "K-"
               << machine << "-" << output_mask;
        return stream.str();
    }

private:
    unsigned int decodeState(char state) {
        assert(state >= 'A' && state <= 'D');
        return static_cast<unsigned int>(state - 'A');
    }

    bool predictsTaken(unsigned int state) {
        assert(state < 4);
        return ((output_mask >> (3 - state)) & 1) != 0;
    }

    unsigned int index_bits;
    std::string machine;
    unsigned int output_mask;
    unsigned int table_entries;
    unsigned char *TABLE;
    unsigned char transitions[4][2];
};

class BTBPredictor : public BranchPredictor
{
public:
	BTBPredictor(int btb_lines, int btb_assoc)
	     : table_lines(btb_lines),
	       table_assoc(btb_assoc),
	       table_sets(btb_lines / btb_assoc),
	       table(btb_lines),
	       lru_clock(0),
	       correct_target_predictions(0),
	       incorrect_target_predictions(0),
	       last_predicted_target_valid(false),
	       last_predicted_target(0)
	{
		assert(table_lines > 0);
		assert(table_assoc > 0);
		assert((table_lines % table_assoc) == 0);
	}

	~BTBPredictor() {
	}

    virtual bool predict(ADDRINT ip, ADDRINT target) {
		Entry *entry = findEntry(ip);

		if (entry != 0) {
			entry->last_used = ++lru_clock;
			last_predicted_target_valid = true;
			last_predicted_target = entry->target;
			return true;
		}

		last_predicted_target_valid = false;
		last_predicted_target = 0;
		return false;
	}

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
		if (predicted && actual) {
			if (last_predicted_target_valid && last_predicted_target == target)
				correct_target_predictions++;
			else
				incorrect_target_predictions++;
		}

		updateCounters(predicted, actual);

		if (!actual)
			return;

		Entry *entry = findEntry(ip);
		if (entry == 0)
			entry = chooseVictim(ip);

		entry->valid = true;
		entry->ip = ip;
		entry->target = target;
		entry->last_used = ++lru_clock;
	}

    virtual string getName() { 
        std::ostringstream stream;
		stream << "BTB-" << table_lines << "-" << table_assoc;
		return stream.str();
	}

    UINT64 getNumCorrectTargetPredictions() { 
		return correct_target_predictions;
	}

    UINT64 getNumIncorrectTargetPredictions() {
		return incorrect_target_predictions;
	}

private:
	struct Entry {
		Entry() : valid(false), ip(0), target(0), last_used(0) {}

		bool valid;
		ADDRINT ip;
		ADDRINT target;
		UINT64 last_used;
	};

	unsigned int setIndex(ADDRINT ip) {
		return (ip >> 4) % table_sets;
	}

	Entry *entryAt(unsigned int set, unsigned int way) {
		return &table[set * table_assoc + way];
	}

	Entry *findEntry(ADDRINT ip) {
		unsigned int set = setIndex(ip);
		for (int way = 0; way < table_assoc; way++) {
			Entry *entry = entryAt(set, way);
			if (entry->valid && entry->ip == ip)
				return entry;
		}
		return 0;
	}

	Entry *chooseVictim(ADDRINT ip) {
		unsigned int set = setIndex(ip);
		Entry *victim = entryAt(set, 0);

		for (int way = 0; way < table_assoc; way++) {
			Entry *entry = entryAt(set, way);
			if (!entry->valid)
				return entry;
			if (entry->last_used < victim->last_used)
				victim = entry;
		}

		return victim;
	}

	int table_lines, table_assoc;
	int table_sets;
	std::vector<Entry> table;
	UINT64 lru_clock;
	UINT64 correct_target_predictions;
	UINT64 incorrect_target_predictions;
	bool last_predicted_target_valid;
	ADDRINT last_predicted_target;
};


// Perceptron class
class PerceptronPredictor : public BranchPredictor
{
	// Perceptrons table size.
	int perceptronTableSize_ = 4096; 
	// History table capacity.
	int historyTableSize_ = 60;
	// The theta value used as the threshold. We use the value found optimal in the paper. (Go read the paper!)
	int kTheta_ = static_cast<int>(1.93 * historyTableSize_ + 14);
	// Start offset for history_.
	int history_start_ = 0;
	// Vector that holds history values
	std::vector<int> history_;
	// The bias, i.e., w_0 for each perceptron. Initialized to 1.
	std::vector<int> bias_;
	// The perceptrons table.
	std::vector<std::vector<int>> weights_;

	// Training the perceptron requires the last predictions output, y. Our update method only provides the prediction as a bool taken/not-taken. We save the last y here and use it on the immediate next 'update' call.
	int last_prediction_y = 0;
public:
	// Constructor
	PerceptronPredictor(int perceptronTableSize, int historyTableSize)
		: BranchPredictor(),
		  perceptronTableSize_(perceptronTableSize),
		  historyTableSize_(historyTableSize),
		  kTheta_(static_cast<int>(1.93 * historyTableSize + 14)) {
        
	history_.resize(historyTableSize_, -1);
        bias_.resize(perceptronTableSize_, 1);
        weights_.resize(perceptronTableSize_, std::vector<int>(historyTableSize_, 0));
        history_start_ = 0;
        last_prediction_y = 0;
    } 

private:
	// Overriden "predict" method...
	// ---
	virtual bool predict(ADDRINT ip, ADDRINT target) {
		int computed_prediction = compute(ip % perceptronTableSize_);
		last_prediction_y = computed_prediction; // Save y to use inside update!
		//std::cout << "I saved: " << prediction << std::endl;
		if (computed_prediction >= 0){
			return true;
		}
		else {
			return false;
		}
  	}
	// ---
	
	
	// Overriden "getName" method...
	// ---
	virtual string getName(){
		std::string output = "Perceptron-M" + std::to_string(perceptronTableSize_) + "-N" + std::to_string(historyTableSize_);
		return output;
  	}
	// ---


	// Overriden "update" method...
	// ---
	virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
		int key = ip % perceptronTableSize_;
		int prediction = last_prediction_y; // Use the saved value y from last prediction 
		int br_taken = 0;
	
		if (actual == true) {
			br_taken = 1;
		}
		else {
			br_taken = -1;
		}
		updateCounters(predicted, actual);
		train(key, prediction, br_taken);
	}
	// ---

	int sign(int val) {
  		return (val >= 0) ? 1 : -1;
	}
  
	// Computes the y value of the perceptron with the given key.
	int compute(int key) {
		int y = bias_[key];
		for (int i = 0; i < historyTableSize_; ++i) {
			int h = ((history_start_ - 1) -i + historyTableSize_) % historyTableSize_;
			y += weights_[key][i] * history_[h];
		}
		return y;
  	}

  	// Trains the perceptron. Takes as inputs:
  	// - key: branch address hashed with table size,
  	// - y: the output y of the last prediction,
  	// - t: the actual result of last prediction (taken/not-taken). This must be 1 for 'taken' and -1 for 'not taken' .
  	void train(int key, int y, int t) {
		// Only train the perceptron if we were wrong or if we didn't give a strong enough response.
		int abs_y = (y < 0) ? -y : y;
		if (sign(y) != t || abs_y <= kTheta_) {
			int b = clampWeight(bias_[key] + t);
			bias_[key] = b;
			
			for (int i = 0; i < historyTableSize_; ++i) {
				int h = ((history_start_ - 1) - i + historyTableSize_) % historyTableSize_;
				int xi = history_[h];
	
				if (t == xi)
					weights_[key][i] = clampWeight(weights_[key][i] + 1);
				else
					weights_[key][i] = clampWeight(weights_[key][i] - 1);
			}
		}
	
		history_[history_start_] = t;
		history_start_ = (1 + history_start_) % historyTableSize_;
	  }

	int clampWeight(int value) {
		if (value > kTheta_)
			return kTheta_;
		if (value < -kTheta_)
			return -kTheta_;
		return value;
	}
};

class TournamentHybridPredictor : public BranchPredictor
{
public:
    TournamentHybridPredictor(unsigned int meta_entries_, BranchPredictor *predictor0_,
                              BranchPredictor *predictor1_, const std::string &name_)
        : BranchPredictor(),
          meta_entries(meta_entries_),
          predictor0(predictor0_),
          predictor1(predictor1_),
          name(name_),
          meta(meta_entries_, 0),
          last_predictor0_prediction(false),
          last_predictor1_prediction(false),
          last_meta_index(0) {
    }

    virtual bool predict(ADDRINT ip, ADDRINT target) {
        last_predictor0_prediction = predictor0->predict(ip, target);
        last_predictor1_prediction = predictor1->predict(ip, target);
        last_meta_index = predictorPcIndex(ip, meta_entries);
        return choosePredictor1(last_meta_index) ? last_predictor1_prediction : last_predictor0_prediction;
    }

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
        predictor0->update(last_predictor0_prediction, actual, ip, target);
        predictor1->update(last_predictor1_prediction, actual, ip, target);

        if (last_predictor0_prediction != last_predictor1_prediction) {
            unsigned int counter = meta[last_meta_index];
            if (last_predictor1_prediction == actual)
                predictorUpdateCounter(counter, 3, true);
            else if (last_predictor0_prediction == actual)
                predictorUpdateCounter(counter, 3, false);
            meta[last_meta_index] = counter;
        }

        updateCounters(predicted, actual);
    }

    virtual string getName() {
        return name;
    }

private:
    bool choosePredictor1(unsigned int meta_index) {
        return predictorCounterTaken(meta[meta_index], 2);
    }

    unsigned int meta_entries;
    BranchPredictor *predictor0;
    BranchPredictor *predictor1;
    std::string name;
    std::vector<unsigned int> meta;
    bool last_predictor0_prediction;
    bool last_predictor1_prediction;
    unsigned int last_meta_index;
};


#endif
