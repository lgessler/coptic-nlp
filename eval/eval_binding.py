import sys, io, re, os
from glob import glob
from argparse import ArgumentParser
from sklearn.metrics import f1_score, precision_score, recall_score
from utils.eval_utils import list_files

PY3 = sys.version_info[0] == 3

script_dir = os.path.dirname(os.path.realpath(__file__)) + os.sep
plain_dir = script_dir + "plain" + os.sep
err_dir = script_dir + "errors" + os.sep

lex = script_dir + ".." + os.sep + "data" + os.sep + "copt_lemma_lex_cplx_2.5.tab"
frq = script_dir + ".." + os.sep + "data" + os.sep + "cop_freqs.tab"
conf = script_dir + ".." + os.sep + "data" + os.sep + "test.conf"
ambig = script_dir + ".." + os.sep + "data" + os.sep + "ambig.tab"

corpora = "C:\\Uni\\Coptic\\git\\corpora\\pub_corpora\\"
victor = corpora + "martyrdom-victor\\martyrdom.victor_TT\\martyrdom.victor.01.tt"

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))

from stacked_tokenizer import StackedTokenizer

ignore = ["̈", "", "̄", "̀", "̣", "`", "̅", "̈", "̂", "︤", "︥", "︦", "⳿", "~", "\n", "̇", "᷍"]


def check_identical_text(gold,pred):

	gold_labs = []
	counter = -1
	pred_chars = pred.replace(" ","").replace("̅","̄").replace("̅","")
	for i, c in enumerate(gold):
		if c == "_":
			gold_labs[-1]=1
			continue
		else:
			gold_labs.append(0)
			counter+=1
		if c != pred_chars[counter]:
			if not c in ignore and pred_chars[counter] in ignore:
				print("non matching char at " + str(i)+":")
				print(gold[i-15:i+1])
				print(pred_chars[counter-15:counter+1])
				sys.exit(0)


def clean(text):
	text = text.replace("."," .").replace("·"," ·").replace(":"," : ")
	uncoptic1 = r'[A-Za-z0-9|]' # Latin or numbers, pipe
	uncoptic2 = r'\[F[^]]+\]'    # Square brackets if they start with F
	uncoptic3 = r'\([^\)]+\)'   # Anything in round brackets
	uncoptic = "("+"|".join([uncoptic1,uncoptic2,uncoptic3])+")"

	text = re.sub(r'.*ⲦⲘⲀⲢⲦⲨⲢⲒⲀ','ⲦⲘⲀⲢⲦⲨⲢⲒⲀ',text,flags=re.MULTILINE|re.DOTALL)
	text = re.sub(uncoptic,'',text)
	text = re.sub(r"\n+",r"\n",text)
	text = re.sub(r" +",r" ",text)

	return text


def run_eval(gold_list, test_list, return_baseline=False):

	gold = ""
	for file_ in gold_list:
		gold += io.open(file_,encoding="utf8").read().strip() + "\n"
	test = ""
	for file_ in test_list:
		test += io.open(file_,encoding="utf8").read().strip() + "\n"
	test = clean(test)

	to_process = []
	for line in test.strip().split("\n"):
		line = line.strip()
		if len(line) == 0:
			continue
		if line.endswith("‐"):
			line = line[:-1]
		else:
			line += " "
		to_process.append(line)


	# Get gold data

	lines = gold.split("\n")
	gold = []
	for line in lines:
		if "orig_group=" in line:
			grp = re.search('orig_group="([^"]*)"',line).group(1).strip()
			gold.append(grp.strip())
	gold = "_".join(gold)

	naive = "".join(to_process)
	check_identical_text(gold,naive)  # Check that gold and input have same number of Coptic characters
	naive = naive.replace(" ","_")

	scores,errs = binding_score(gold,naive)
	print("Baseline f-score:")
	print(scores["f1"])

	if return_baseline:
		return scores

	baseline_f1 = scores["f1"]

	stk = StackedTokenizer(no_morphs=True,model="test",pipes=True,detok=2,tokenized=True)
	stk.load_ambig(ambig_table=ambig)

	bound = stk.analyze("\n".join(to_process)).replace("|","").replace('\n','').strip()

	scores, errs = binding_score(gold,bound)
	scores["baseline"] = baseline_f1

	with io.open(err_dir + "errs_binding.tab",'w',encoding="utf8") as f:
		f.write("\n".join(errs) + "\n")

	print("Binding f-score:")
	print(scores["f1"])

	return scores


def binarize(text):
	"""Turn a text with _ separating boundgroups into array of 0 (no split after character) or 1 (split after
	this character)

	Input: auO_prOme_...
	Output: [0,0,1,0,0,0,0,1,...]
	"""
	output = []

	for c in text:
		if c in ignore:
			continue
		if c == "_" and len(output) > 0:
			output[-1] = 1
		else:
			output.append(0)
	return output


def binding_score(gold,pred):

	bin_gold = binarize(gold)
	bin_pred = binarize(pred)

	gold_reached = 0
	pred_reached = 0
	gold_groups = gold.split("_")
	pred_groups = pred.split("_")
	errs = []
	for i,c in enumerate(range(len(bin_gold))):
		if bin_gold[i] == 1:
			gold_reached +=1
		if bin_pred[i] == 1:
			pred_reached +=1
		if bin_gold[i] != bin_pred[i]:
			gold_start = gold_end = gold_reached + 1
			pred_start = pred_end = pred_reached + 1
			if gold_reached > 0:
				pass
				gold_start = gold_reached-1
			if pred_reached > 0:
				pass
				pred_start = pred_reached -1
			if gold_reached < len(gold_groups)-1:
				gold_end = gold_reached +2
			if pred_reached < len(pred_groups) -1:
				pred_end = pred_reached +2
			errs.append(" ".join(gold_groups[gold_start:gold_end]) + "\t" + " ".join(pred_groups[pred_start:pred_end]))

	scores = {}
	scores["f1"] = f1_score(bin_gold,bin_pred)
	scores["precision"] = precision_score(bin_gold,bin_pred)
	scores["recall"] = recall_score(bin_gold,bin_pred)

	return scores, errs


if __name__ == "__main__":
	# Get just Coptic chars and whitespace

	p = ArgumentParser()
	p.add_argument("--train_list",default="victor_tt",help="file with one file name per line of TT SGML training files or alias of train set, e.g. 'silver'; all files not in test if not supplied")
	p.add_argument("--test_list",default="victor_plain",help="file with one file name per line of plain text test files, or alias of test set, e.g. 'ud_test'")
	p.add_argument("--file_dir",default="plain",help="directory with plain text files")
	p.add_argument("--gold_dir",default="unreleased",help="directory with gold .tt files")

	opts = p.parse_args()

	if os.path.isfile(opts.test_list):
		test_list = io.open(opts.test_list,encoding="utf8").read().strip().split("\n")
		test_list = [script_dir + opts.file_dir + os.sep + f for f in test_list]
	else:
		test_list = list_files(opts.test_list)

	if opts.train_list is not None:
		if os.path.isfile(opts.train_list):
			train_list = io.open(opts.train_list,encoding="utf8").read().strip().split("\n")
			train_list = [script_dir + opts.gold_dir + os.sep + f for f in train_list]
		else:
			train_list = list_files(opts.train_list)
	else:
		train_list = glob(script_dir + opts.gold_dir + os.sep + "*.tt")
		train_list = [os.path.basename(f) for f in train_list if os.path.basename(f) not in test_list]
		train_list = [script_dir + opts.gold_dir + os.sep + f for f in train_list]


	scores = run_eval(train_list,test_list)


