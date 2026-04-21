#ifndef BRANCH_PREDICTOR_H
#define BRANCH_PREDICTOR_H

#include <sstream> // std::ostringstream
#include <cmath>   // pow()
#include <cstring> // memset()

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
    ~NbitPredictor() { delete TABLE; };

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

// Fill in the BTB implementation ...
class BTBPredictor : public BranchPredictor
{
public:
	BTBPredictor(int btb_lines, int btb_assoc)
	     : table_lines(btb_lines), table_assoc(btb_assoc)
	{
		/* ... fill me ... */
	}

	~BTBPredictor() {
		/* ... fill me ... */
	}

    virtual bool predict(ADDRINT ip, ADDRINT target) {
		/* ... fill me ... */
		return false;
	}

    virtual void update(bool predicted, bool actual, ADDRINT ip, ADDRINT target) {
		/* ... fill me ... */
	}

    virtual string getName() { 
        std::ostringstream stream;
		stream << "BTB-" << table_lines << "-" << table_assoc;
		return stream.str();
	}

    UINT64 getNumCorrectTargetPredictions() { 
		/* ... fill me ... */
		return 0;
	}

private:
	int table_lines, table_assoc;
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
	PerceptronPredictor(int perceptronTableSize, int historyTableSize) : BranchPredictor(), perceptronTableSize_(perceptronTableSize), historyTableSize_(historyTableSize) {
        
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
		std::string output = "Perceptron Branch Predictor (perceptrons: " + std::to_string(perceptronTableSize_) + ", history size: " + std::to_string(historyTableSize_);
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
		if (sign(y) != t || abs(y) <= kTheta_) {
		  	int b = bias_[key] + t;
		  	bias_[key] = b;
			
			for (int i = 0; i < historyTableSize_; ++i) {
				int h = ((history_start_ - 1) - i + historyTableSize_) % historyTableSize_;
				int xi = history_[h];
	
				if (t == xi)
					weights_[key][i] += 1;
				else
					weights_[key][i] -= 1;
			}
		}
	
		history_[history_start_] = t;
		history_start_ = (1 + history_start_) % historyTableSize_;
	  }
};


#endif
