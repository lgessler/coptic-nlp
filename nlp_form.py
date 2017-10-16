#!/usr/bin/python
# -*- coding: utf-8 -*-

# V1.3.0

import os
import re
import cgi, cgitb
import tempfile
import subprocess
import requests
import platform
import _version
from depedit import DepEdit


def groupify_norms(output):
	groups = ""
	current_group = ""
	for line in output.split("\n"):
		if line.startswith("<norm "):
			current_group += re.search(r'norm="([^"]+)"',line).group(1)
		if line.startswith("</norm_group"):
			groups += current_group +"\n"
			current_group = ""

	return groups


def read_attributes(input,attribute_name):
	out_stream =""
	for line in input.split('\n'):
		if attribute_name + '="' in line:
			m = re.search(attribute_name+r'="([^"]*)"',line)
			if m is None:
				print("ERR: cant find " + attribute_name + " in line: " + line)
				attribute_value = ""
			else:
				attribute_value = m.group(1)
			if len(attribute_value)==0:
				attribute_value = "_warn:empty_"+attribute_name+"_"
			out_stream += attribute_value +"\n"
	return out_stream

def exec_via_temp(input_text, command_params, workdir=""):
	temp = tempfile.NamedTemporaryFile(delete=False)
	exec_out = ""
	try:
		temp.write(input_text)
		temp.close()

		command_params = [x if x != 'tempfilename' else temp.name for x in command_params]
		if workdir == "":
			proc = subprocess.Popen(command_params, stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
			(stdout, stderr) = proc.communicate()
		else:
			proc = subprocess.Popen(command_params, stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE,cwd=workdir)
			(stdout, stderr) = proc.communicate()

		exec_out = stdout
	except Exception as e:
		print(e)
	finally:
		os.remove(temp.name)
		return exec_out

def merge_via_temp(input1,input2,command_params,workdir=""):
	temp1 = tempfile.NamedTemporaryFile(delete=False)
	temp2 = tempfile.NamedTemporaryFile(delete=False)
	output = ""
	try:
		temp1.write(input1)
		temp1.close()
		temp2.write(input2)
		temp2.close()

		command_params = [x if x != 'tempfilename1' else temp1.name for x in command_params]
		command_params = [x if x != 'tempfilename2' else temp2.name for x in command_params]

		if workdir == "":
			proc = subprocess.Popen(command_params, stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
		else:
			proc = subprocess.Popen(command_params, stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE,cwd=workdir)

		output = proc.stdout.read()

	finally:
		os.remove(temp1.name)
		os.remove(temp2.name)
		return output


def get_origs(data):
	origs = []
	current = ""
	for line in data.split("\n"):
		if "</norm>" in line:
			origs.append(current)
			current = ""
		if not line.startswith("<"):  # Token line
			current += line

	return "\n".join(origs)


def inject(attribute_name, contents, at_attribute,into_stream,replace=True):
	insertions = contents.split('\n')
	injected = ""
	i=0
	for line in into_stream.split("\n"):
		if at_attribute + "=" in line:
			if len(insertions[i])>0:
				if at_attribute == attribute_name:  # Replace old value of attribute with new one
					line = re.sub(attribute_name+'="[^"]+"',attribute_name+'="'+insertions[i]+'"',line)
				else:  # Place before specific at_attribute
					if replace or " " + attribute_name + "=" not in line:
						line = re.sub(at_attribute+"=",attribute_name+'="'+insertions[i]+'" '+at_attribute+"=",line)
			i += 1
		injected += line + "\n"
	return injected


def extract_conll(conll_string):
	conll_string = conll_string.replace("\r","")
	sentences = conll_string.split("\n\n")
	ids = ""
	funcs = ""
	parents = ""
	id_counter = 0
	offset = 0
	for sentence in sentences:
		tokens = sentence.split("\n")
		for token in tokens:
			if "\t" in token:
				id_counter +=1
				ids += "u"+ str(id_counter) + "\n"
				cols = token.split("\t")
				funcs += cols[7].replace("ROOT","root") +"\n"
				if cols[6] == "0":
					parents += "#u0\n"
				else:
					parents += "#u" + str(int(cols[6])+offset)+"\n"
		offset = id_counter
	return ids, funcs, parents


def nlp_coptic(input,lb,parse_only=False, do_tok=True, do_norm=True, do_tag=True, do_lemma=True, do_lang=True, do_milestone=True, do_parse=True, sgml_mode="sgml", tok_mode="auto", secure=False,exp_tok=False):

	from paths import tt_path, conllize_path, tokenizer_path, parser_path, norm_path, lang_path, milestone_path, depedit_path, stacked_tok_path, python3
	plain_test="""	ⲁ<hi rend="red">ϥ</hi>ⲥⲱⲧ︤ⲙ︥_ⲛ̄ϭⲓⲡⲁⲅⲅⲉⲗⲟⲥ"""
	data=input
	data=data.replace("\t","")
	data=data.replace("\r","")

	if len(data) > 20000 and not secure:
		return "Input was too long; demo version limited to 10000 characters"
	else:
		if do_milestone:
			milestone = ['perl',milestone_path+'binarize_tags.pl','tempfilename']
			data = exec_via_temp(data,milestone)
		if sgml_mode == "sgml":
			if exp_tok and tok_mode != "from_pipes":
				tokenize = [python3, stacked_tok_path + 'stacked_tokenizer.py']
			else:
				tokenize = ['perl',tokenizer_path+'tokenize_coptic.pl']
				tokenize += ['-d', tokenizer_path + 'copt_lex.tab', '-s', tokenizer_path + 'segmentation_table.tab',
							 '-m', tokenizer_path + 'morph_table.tab']
			if lb == "line":
				tokenize.append('-l')
			if tok_mode == "from_pipes":
				tokenize.append('-t')
			tokenize += ['tempfilename']
		else:
			if lb == "line":
				if exp_tok:
					tokenize = [python3,stacked_tok_path+'stacked_tokenizer.py','-p','-l','tempfilename']
				else:
					tokenize = ['perl',tokenizer_path+'tokenize_coptic.pl','-n','-p','-l','-d',tokenizer_path+'copt_lex.tab','-s',tokenizer_path+'segmentation_table.tab','-m',tokenizer_path+'morph_table.tab','tempfilename']
			else:
				if exp_tok:
					tokenize = [python3,stacked_tok_path+'stacked_tokenizer.py','-p','tempfilename']
				else:
					tokenize = ['perl',tokenizer_path+'tokenize_coptic.pl','-n','-p','-d',tokenizer_path+'copt_lex.tab','-s',tokenizer_path+'segmentation_table.tab','-m',tokenizer_path+'morph_table.tab','tempfilename']

			if exp_tok:
				tokenized = exec_via_temp(data,tokenize,stacked_tok_path)
			else:
				tokenized = exec_via_temp(data,tokenize)
			tokenized = tokenized.replace('\r','').strip()
			tokenized = re.sub(r'_$','',tokenized)
			if lb != "line":
				tokenized = tokenized.replace("\n","")
			return tokenized

		if do_tok:
			if exp_tok:
				tokenized = exec_via_temp(data,tokenize,stacked_tok_path)
			else:
				tokenized = exec_via_temp(data,tokenize)
		else:
			tokenized = data
			if sgml_mode == "sgml":
				tok_lines = []
				for line in tokenized.split("\n"):
					out_line = '<norm_group norm_group="' + line + '">\n<norm norm="'+ line +'">\n' + line + '\n</norm>\n</norm_group>'
					tok_lines.append(out_line)
				tokenized = "\n".join(tok_lines)
		tokenized = tokenized.replace('\r','').strip()
		with open("/var/www/html/gitdox/scriptorium/debug.txt",'w') as f:
			f.write(tokenized)
		output = tokenized
		norms = read_attributes(tokenized,"norm")

		if do_norm:
			normalize = ['perl', norm_path+'auto_norm.pl','-t',norm_path+'norm_table.tab','tempfilename']
			normalized = exec_via_temp(norms,normalize)
			norms = re.sub('\r','',normalized)
			output = inject("norm", norms, "norm", output)

		if parse_only:
			tag = [tt_path+'bin'+os.sep+'tree-tagger', tt_path+'bin'+os.sep+'coptic_fine10.par', '-token','-lemma','-no-unknown', '-sgml' ,'tempfilename'] #no -token
			tagged = exec_via_temp(norms,tag)
			tagged = re.sub('\r','',tagged)
			conllize = ['perl', conllize_path+'TT2CoNLL.pl','-t','PUNCT','tempfilename']
			conllized = exec_via_temp(tagged,conllize)
			conllized = re.sub("\t0\t","\t_\t",conllized)
			conllized = re.sub("\r","",conllized)
			parse_coptic = ['java','-mx512m','-jar',"maltparser-1.8.jar",'-c','coptic','-i','tempfilename','-m','parse']
			parsed = exec_via_temp(conllized,parse_coptic,parser_path)
			return parsed
		elif not do_parse:
			tag = [tt_path+'bin'+os.sep+'tree-tagger', tt_path+'bin'+os.sep+'coptic_fine10.par', '-lemma','-no-unknown', '-sgml' ,'tempfilename'] #no -token
			tagged = exec_via_temp(norms,tag)
			tagged = re.sub('\r','',tagged)
		if do_parse:
			tag = [tt_path+'bin'+os.sep+'tree-tagger', tt_path+'bin'+os.sep+'coptic_fine10.par', '-token','-lemma','-no-unknown', '-sgml' ,'tempfilename'] #no -token
			tagged = exec_via_temp(norms,tag)
			tagged = re.sub('\r','',tagged)
			conllize = ['perl', conllize_path+'TT2CoNLL.pl','-t','PUNCT','tempfilename']
			conllized = exec_via_temp(tagged,conllize)
			conllized = re.sub("\t0\t","\t_\t",conllized)
			conllized = re.sub("\r","",conllized)
			parse_coptic = ['java','-mx512m','-jar',"maltparser-1.8.jar",'-a','stackeager','-c','coptic','-i','tempfilename','-m','parse']
			parsed = exec_via_temp(conllized,parse_coptic,parser_path)
			deped = DepEdit(open(depedit_path + "parser_postprocess_nodom.ini"))
			depedited = deped.run_depedit(parsed.split("\n"))
			ids, funcs, parents = extract_conll(depedited)
			tagged = re.sub(r"(^|\n)[^\t]+\t",r"\1",tagged)

		lemmas = re.sub('^[^\t]+\t','',tagged)
		lemmas = re.sub('\n[^\t]+\t','\n',lemmas)
		tagged = re.sub('(\t[^\t]+\n)','\n',tagged)
		lang = ['perl', lang_path+'_enrich_no_encode.pl','-l',lang_path + 'language-tagger' + os.sep + 'lexicon.txt','tempfilename']
		langed = exec_via_temp(norms,lang)
		langed = re.sub(r'\n[^\t\n\r]+','\n',langed)
		langed = re.sub(r'^[^\t\n\r]+','',langed)
		langed = re.sub('\r','',langed)
		langed = re.sub(r'\t','',langed)


		if do_parse:
			output = inject("xml:id",ids,"norm",output)
		if do_tag:
			output = inject("pos",tagged,"norm",output)
		if do_lemma:
			output = inject("lemma",lemmas,"norm",output)
		if do_lang:
			output = inject("xml:lang",langed,"norm",output)
		if do_parse:
			output = inject("func",funcs,"norm",output)
			output = inject("head",parents,"norm",output)
			output = output.replace(' head="#u0"',"")

		if "norm_group=" in tokenized:
			orig_groups = read_attributes(tokenized,"norm_group")
		elif "orig_group=" in tokenized:
			orig_groups = read_attributes(tokenized,"orig_group")
		else:
			orig_groups = ""


		output = re.sub(r"<norm_group norm_group=","<norm_group orig_group=",output)
		if do_norm and len(orig_groups) > 0:
			groups = groupify_norms(output)
			output = inject("norm_group",groups,"orig_group",output)

			# Add orig from tokens based on norm spans
			origs = get_origs(output)
			output = inject("orig",origs,"norm",output)

		return output


def get_menu():
	cs = "http://copticscriptorium.org/nav.html"
	try:
		resp = requests.get(cs)
	except:
		return ""
	return resp.text


def make_nlp_form(access_level, mode):
	if platform.system() == 'Linux':
		action_dest = ''
		secure_dest = 'secure'
	else:
		action_dest = 'index.py'
		secure_dest = 'secure.py'


	if access_level == "secure":
		access_message = """				<p>Enter Coptic text in UTF-8 (XML markup is also allowed). <br/>
				Bound groups should be separated by <b>spaces</b> or <b>underscores</b>.</p>"""
		action_dest = secure_dest
	else:
		access_message = '''			<p>Enter Coptic text in UTF-8 (XML markup is also allowed, 10,000 characters max). <br/>
				Bound groups should be separated by <b>spaces</b> or <b>underscores</b>.</p>
				<p>If you need to analyze longer texts or multiple texts automatically, you can log in
				to the <a href="'''+secure_dest+'''">secure</a> area or use the <a href="api">API</a>. For a login please
				contact <a href="http://corpling.uis.georgetown.edu/amir/">Amir Zeldes</a>.
				</p>'''

	if mode == "interactive":
		output = ""
		data = """ⲁ<hi rend="red">ϥ</hi>ⲥⲱⲧ︤ⲙ︥ ⲛ̄ϭ
ⲓⲡⲁⲅⲅⲉⲗⲟⲥ ⲙ̄ⲙ︤ⲛ︦ⲧ︥ϣⲃⲏⲣ"""
		form = cgi.FieldStorage()
		processed=""
		lb = "noline"
		exp_tok = False
		sgml_mode = "sgml"
		tok_mode = "auto"
		do_lemma = True
		do_tag = True
		do_parse = True
		do_tok = True
		do_norm = True
		do_lang = True
		do_milestone = True
		if "data" in form:
			data = form.getvalue("data")
			data = re.sub(r'\r','',data)
			data = data.strip()
			lb = form.getvalue("lb")
			exp_tok = form.getvalue("exp_tok") is not None
			sgml_mode = form.getvalue("sgml_mode")
			tok_mode = form.getvalue("tok_mode")
			do_milestone = form.getvalue("milestone") is not None
			do_lemma = form.getvalue("lemma") is not None
			do_tag = form.getvalue("tag") is not None
			do_parse = form.getvalue("parse") is not None
			do_norm = form.getvalue("norm") is not None
			do_tok = form.getvalue("tok") is not None
			do_lang = form.getvalue("lang") is not None
			processed = nlp_coptic(data,lb,False,do_tok,do_norm,do_tag,do_lemma,do_lang,do_milestone,do_parse,sgml_mode,tok_mode,access_level=="secure",exp_tok)
			processed = processed.strip()
		data = re.sub(r'\r','',data)

		output += '''<html>
				<head>
					<title>Coptic NLP Service</title>
					<link rel="stylesheet" href="css/scriptorium.css" type="text/css" charset="utf-8"/>
					<link rel="stylesheet" href="css/font-awesome-4.2.0/css/font-awesome.min.css"/>
					<meta charset="UTF-8"/>
					<meta name="viewport" content="width=800">
					<link rel="shortcut icon" href="favicon.ico" type="image/x-icon">
					<link rel="icon" href="favicon.ico" type="image/x-icon">
					<script>var __adobewebfontsappname__="dreamweaver"</script>
					<link rel="stylesheet" href="https://use.edgefonts.net/c/dbcb1c/1w;asul,2,WXx:W:n4/l" media="all">
					<script src="http://use.edgefonts.net/asul:n4:default.js" type="text/javascript"></script>
				</head>
				<body>
					**navbar**
					<div id="header">
						<div id="copticlogo">
							<a href="http://copticscriptorium.org/">
								<img id="img1" src="https://corpling.uis.georgetown.edu/coptic-nlp/img/copticlogo.png" width="210" height="101" alt="Coptic SCRIPTORIUM"/>
							</a>
						</div>
						<div id="unicorn">
							<a href="http://copticscriptorium.org/">
								<img id="img2" src="https://corpling.uis.georgetown.edu/coptic-nlp/img/unicorn.png" width="80" height="101" alt="Unicorn"/>
							</a>
						</div>
						<div id="englishlogo">
							<a href="http://copticscriptorium.org/">
								<img id="img3" src="https://corpling.uis.georgetown.edu/coptic-nlp/img/englishlogo.png" width="199" height="101" alt="Coptic SCRIPTORIUM"/>
							</a>
						</div>
						<img id="img4" src="img/ruleline.png" width="800px" height="14" alt=""/>
						</br>
						</br>
					</div>
				<form id="nlp_form" class="nlp_form" method="post" action="/coptic-nlp/''' + action_dest + '''">
			<h2>Coptic NLP Service</h2>
				'''+access_message+'''
			<div>
			<h3>Input:</h3>
				<input type="radio" name="lb" value="line" '''
		if lb != "noline":
			output+= 'checked="checked"'
		output += '''>My data contains meaningful linebreaks
					<a href="#" class="tooltip2">
						<i class="fa fa-info-circle" style="display: inline-block"></i>
    					<span>
							<img class="callout" src="img/callout.gif" />
							This inserts &lt;line&gt;..&lt;/line&gt; tags around each line of text.</br>
							If you already have &lt;lb/&gt; tags or your data is already tokenized, you
							probably want to ignore line breaks.
							<br/>
						</span>
					</a>
				</input>
				<br/>
				<input type="radio" name="lb" value="noline"'''
		if lb == "noline":
			output+= 'checked="checked"'
		tok_checked = ' checked="checked"' if do_tok else ""
		exp_checked = ' checked="checked"' if exp_tok else ""
		norm_checked = ' checked="checked"' if do_norm else ""
		tag_checked = ' checked="checked"' if do_tag else ""
		lemma_checked = ' checked="checked"' if do_lemma else ""
		parse_checked = ' checked="checked"' if do_parse else ""
		lang_checked = ' checked="checked"' if do_lang else ""
		milestone_checked = ' checked="checked"' if do_milestone else ""

		output+='''>Ignore linebreaks in my data</input>
		<br/>
		<h3>Output:</h3>
		<table>
		<tr><td colspan="2" style="padding-bottom: 10px"><input type="checkbox" name="exp_tok" value="exp_tok"'''
		if exp_tok:
			output+= exp_checked
		output += '''>Use experimental tokenizer <span style="color: gray; font-size:small"><tt>[stk-&alpha;-0.9.1]</tt></span>
		<a href="#" class="tooltip2">
						<i class="fa fa-info-circle" style="display: inline-block"></i>
    					<span>
							<img class="callout" src="img/callout.gif" />
							Highly experimental. </br>Should be more accurate but less stable.
							Crashes are possible.
							<br/>
						</span>
					</a></input><br/></td></tr>
		<tr><td>
			<input type="radio" name="sgml_mode" value="sgml" onclick="disable_checkboxes(false);"'''
		if sgml_mode == "sgml":
			output+= ' checked="checked"'
		output += '''>SGML pipeline</input><br/>
			<ul>
				<input type="checkbox" id="milestone" name="milestone" value="milestone"'''+milestone_checked+'''>Stretch milestones
				<a href="#" class="tooltip2">
					<i class="fa fa-info-circle" style="display: inline-block"></i>
    				<span>
						<img class="callout" src="img/callout.gif" />
						This setting replaces unary XML elements with binary ones. For example for
						milestone page break elements: (&lt;pb/&gt; &rarr; &lt;pb&gt; ... &lt;/pb&gt;)
						<br/>
    				</span>
				</a>
				</input><br/>
				<input type="checkbox" id="tok" name="tok" value="tok"'''+tok_checked+'''>Tokenize</input>
				<ul style="padding-left: 20px;">
					<input type="radio" name="tok_mode" value="auto"'''
		if tok_mode == "auto":
			output+= 'checked="checked"'
		output += '''>Automatic</input><br/>
					<input type="radio" name="tok_mode" value="from_pipes"'''
		if tok_mode == "from_pipes":
			output+= 'checked="checked"'
		output +='''>From pipes in input</input>
				</ul>
				<input type="checkbox" id="norm" name="norm" value="norm"'''+norm_checked+'''>Normalize
				<a href="#" class="tooltip2">
					<i class="fa fa-info-circle" style="display: inline-block"></i>
    				<span>
						<img class="callout" src="img/callout.gif" />
						Disable to remove norm_group attribute from output.<br/>
						Diacritic stripping will still be done for processing norm units.
						<br/>
    				</span>
				</a>
				</input><br/>
				<input type="checkbox" id="tag" name="tag" value="tag"'''+tag_checked+'''>Tag</input><br/>
				<input type="checkbox" id="lemma" name="lemma" value="lemma"'''+lemma_checked+'''>Lemmatize</input><br/>
				<input type="checkbox" id="lang" name="lang" value="lang"'''+lang_checked+'''>Language of origin</input><br/>
				<input type="checkbox" id="parse" name="parse" value="parse"'''+parse_checked+'''>Parse</input>
			</ul>
		</td>
		<td style="vertical-align: top; padding-left: 20px">
			<input type="radio" name="sgml_mode" value="pipes" onclick="disable_checkboxes(true);"'''
		if sgml_mode != "sgml":
			output+= ' checked="checked"'

		output += '''>Just piped and dashed morphemes
			</input>
		</td>
		</tr>
		</table>
		</div>
		<div>
			<textarea class="anti nlp_input" id="data" name="data" type="textarea">'''
		output += data + '''</textarea>
			</div>
			<div><button type="submit" onclick="isValidForm()">Process</button></div>
			<div>
				<p>Result:</p>
				<textarea class="anti nlp_input" id="result" type="textarea">'''
		output += processed
		output += '''</textarea></div>
				</form>'''


		output += """
		<script>
		document.getElementById('nlp_form').onsubmit = function() {
			return false;
		};
		function isValidForm(){"""
		if access_level == "secure":
			output += """						document.getElementById("nlp_form").submit();
						return true;
						"""
		else:
			output += """
					if (document.getElementById("data").value.length > 10000){
						alert("You entered " + document.getElementById("data").value.length + " characters. Please enter no more than 10000 characters.");
						return false;
					}
					else{

						document.getElementById("nlp_form").submit();
						return true;
					}"""
		output += """
		}
		</script>
<div id="bottomcontent">
<div id="footer">
<p><a class="github" href="https://github.com/CopticScriptorium" target="new"> Fork us on GitHub</a><br></p>

<p><a class="twitter" href="https://twitter.com/copticscript" target="_blank"> Follow Coptic SCRIPTORIUM on Twitter</a></p>

<p>Coptic SCRIPTORIUM is supported by <br><a href="http://www.neh.gov" target="_blank">the National Endowment for the Humanities</a> <a href="http://www.neh.gov/divisions/odh" target="_blank">Office of Digital Humanities</a> and <a href="http://www.neh.gov/divisions/preservation" target="_blank">Division of Preservation and Access</a>,<br>
<a href="www.pacific.edu" target="blank">the University of the Pacific</a>, <a href="http://www.georgetown.edu" target="_blank">Georgetown University</a>, and <a href="http://www.canisius.edu" target="_blank">Canisius College</a>.</p>
      <img id="img5" alt="Seal of the University of the Pacific" src="img/Seal_White_RGB.png" height="62px" longdesc="http://www.pacific.edu">&nbsp;&nbsp;&nbsp;<img id="img6" src="img/georgetown-seal-white.png" height="62px" alt="GeorgetownUniversitySeal" longdesc="http://www.georgetown.edu">&nbsp;&nbsp;&nbsp;<img id="img8" src="img/CC_logo_white+109U.png" height="40px" alt="CanisiusCollegeLogo" longdesc="http://www.canisius.edu">&nbsp;&nbsp;&nbsp;<img id="img7" src="img/neh_logo_horizontal_4cprev_u-0.png" width="252" height="62" alt="neh logo" longdesc="http://www.neh.gov">
      <br>
  </div>

</div>
	<script>
		function disable_checkboxes(val){
			document.getElementById("milestone").disabled = val;
			document.getElementById("tok").disabled = val;
			document.getElementById("tag").disabled = val;
			document.getElementById("lemma").disabled = val;
			document.getElementById("lang").disabled = val;
			document.getElementById("norm").disabled = val;
			document.getElementById("parse").disabled = val;
			radios = document.getElementsByName("tok_mode");
			for (radio in radios){
				radios[radio].disabled = val;
			}
			if (val == false){
				document.getElementById("milestone").checked = true;
				document.getElementById("tok").checked = true;
				document.getElementById("tag").checked = true;
				document.getElementById("lemma").checked = true;
				document.getElementById("lang").checked = true;
				document.getElementById("norm").checked = true;
				document.getElementById("parse").checked = true;
			}
		}

		if (document.querySelector('input[name="sgml_mode"]:checked').value == "pipes"){
			disable_checkboxes(true);
		}
	</script>
</body>
</html>"""

		menu = get_menu()
		menu = menu.encode("utf8")
		output = output.replace("**navbar**",menu)
		output = output.replace("\n\t\t","\n\t")
		return output
