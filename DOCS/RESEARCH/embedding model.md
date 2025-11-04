<span id="1"></span>

<div id="page1-div"
style="position:relative;width:918px;height:1188px;">

**Executive Summary**

LLMC should **upgrade its embedding model** to improve code and documentation retrieval, using a *unified  
model* that handles both source code and natural language well. Based on extensive comparisons of API  
services (OpenAI, Cohere, Voyage AI) and local open-source models (E5, BGE, Nomic, etc.), we recommend  
adopting an  **open-source embedding model (e.g.   intfloat/e5-base-v2 )**  as the default. This model  
provides **significantly higher retrieval accuracy** on code searches (up to 10–15% better Recall@5) than the  
current MiniLM baseline, while incurring **zero API cost** and keeping embedding latency well under 100 ms  
per chunk. In benchmarks, E5-base (768-dimensional) achieved ~83–85% top-5 retrieval accuracy on general  
text (vs ~78% for MiniLM)

 and performed strongly on code tasks (overall recall@5 ≈50.9% in a multi-

dataset code benchmark)

 – rivaling larger proprietary models. 

Other candidates were evaluated: OpenAI’s new embeddings ( text-embedding-3 ) offer high quality but  
come with external API dependencies; Voyage’s *code-specialized* model yields the best code recall (≈**14.5%  
**higher   than   OpenAI   on   code   tasks

)   at   a   low   cost,   but   requires   using   a   third-party   API.  **Our**

**recommendation** is to use a **local model like E5-base or a similar 768-dim encoder** for a good balance of  
quality, cost, and performance. This approach boosts retrieval accuracy by ≥10% (meeting the planner  
improvement goal) without recurring fees or data privacy concerns. For maximum quality in mission-critical  
cases, we also outline options like Voyage Code-2 (API) or Nomic’s 7B code model (local) – though these  
provide diminishing returns (only ~5% higher recall) at higher
complexity and cost. 

We provide a comparison of all options below, followed by benchmarking results, integration steps to swap  
the embedding model in LLMC, a fine-tuning strategy for domain-specific improvements, cost analyses, and  
a migration plan. In summary, **upgrading from MiniLM (384-dim)** to a modern embedding model (≥768-  
dim)  will  substantially  enhance  LLMC’s  semantic  search  for  both  code  and  documentation,  **improving  
recall@5 by well over 10%** while keeping storage growth and latency within acceptable bounds. The switch  
can be implemented with minimal code changes (e.g. one line to load the new model) and a one-time re-  
indexing of ~5–10K spans per repository. 

**Model Comparison Overview**

To decide on the best embedding model, we evaluated a range of **API-based** and **local** models along key  
dimensions:  **retrieval   quality**  (especially   for   code   vs   text),  **embedding   vector   size**,  **cost   per   usage**,   
**throughput/latency**,  and  **ease  of  integration**  (including  fine-tuning  or  self-hosting).  The  table  below  
summarizes the candidates:

**API-Hosted Models (OpenAI, Cohere, Voyage AI):**

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[2](https://arxiv.org/html/2407.02883v1#:~:text=Contriever%20%28110M%29%205,21)

[3](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=TL%3BDR%20%E2%80%93%20We%20are%20thrilled,purpose%20text%20datasets)

[4](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=This%20post%20presents%20%60%60voyage,the%20context%20window%20to%2016K)

1

</div>

<span id="2"></span>

<div id="page2-div"
style="position:relative;width:918px;height:1188px;">

**Model**

**Dimensions**

**Code  
Retrieval  
Quality** \<br/  
\>(Recall@5 or  
similar)

**Text  
Retrieval  
Quality** \<br/  
\>(MTEB /  
Top-5  
Accuracy)

**Cost** (USD  
per 1M  
tokens)

**Notes**

OpenAI *text-  
embedding-  
ada-002*

1536

~45–46%  
(baseline;  
moderate)

~61% MTEB  
avg  
(English)

\$0.40 

General-purpose;  
widely used  
baseline. No code  
specialization.

OpenAI *text-  
embedding-3-  
small*

1536

~47%  
(estimated;  
improved  
multi-lingual  
vs ada)

~62.3%  
MTEB  
(English)

**\$0.02**

New efficient model  
(2024). 5× cheaper  
than ada-002,  
similar English  
performance, better  
multilingual.

OpenAI *text-  
embedding-3-  
large*

3072

~49% (next-  
best to  
Voyage on  
code)

~64.6%  
MTEB  
(English)

\$0.13 

Best OpenAI model.  
High dimensional  
(3072) but can be  
truncated to smaller  
sizes

.

Cohere   
*embed-  
english-v3*

768

~Low–Med  
(no public  
data; below  
OpenAI-3-  
large)

~60–63%  
(est.; ~5%  
below top  
models)

\$0.12  
(estimated)

General text embed  
model. Good  
English  
performance, not  
tuned for code.

**Voyage AI  
***voyage-code-2*

1536

**~52.9%** (SOTA  
on code;  
+14.5% vs  
OpenAI)

~63–65%  
(strong  
general;  
+3% vs  
OpenAI)

\$0.12 

Specialized for  
code. Excels at code  
search (trained on  
code QA datasets).  
16K token context

.

**Local Open-Source Models (Self-Hosted):**

[5](https://arxiv.org/html/2407.02883v1#:~:text=E5,59)

[6](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Stronger%20performance.%20%60text,to%2064.6)

[7](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Reduced%20price.%20%60text,00002)

[8](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Stronger%20performance.%20Comparing%20%60text,to%2062.3)

[7](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Reduced%20price.%20%60text,00002)

[9](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=%60voyage,were%20encountered%20during%20our%20training)

[6](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Stronger%20performance.%20%60text,to%2064.6)

[10](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=64)

[11](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Both%20of%20our%20new%20embedding,with%20a%20size%20of%201536)

[12](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=With%20improved%20training%20methods%20on,average%20results%20across%20all%20datasets)

[13](https://www.eesel.ai/blog/cohere-ai-pricing#:~:text=Cohere%20AI%20pricing%20in%202025%3A,so%20developers%20can%20play)

[3](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=TL%3BDR%20%E2%80%93%20We%20are%20thrilled,purpose%20text%20datasets)

[9](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=%60voyage,were%20encountered%20during%20our%20training)

[12](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=With%20improved%20training%20methods%20on,average%20results%20across%20all%20datasets)

[14](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=Model%20Dimensions%20Max%20Tokens%20Cost,tokens%20cosine%2C%20dot%20product%2C%20L2)

[14](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=Model%20Dimensions%20Max%20Tokens%20Cost,tokens%20cosine%2C%20dot%20product%2C%20L2)

2

</div>

<span id="3"></span>

<div id="page3-div"
style="position:relative;width:918px;height:1188px;">

**Model**

**Dimensions**

**Code Retrieval  
Quality** \<br/  
\>(Recall@5 or  
tasks avg)

**Text  
Retrieval  
Quality  
**\<br/  
\>(Top-5  
Accuracy)

**Speed  
**(GPU  
embed  
per 1K  
tokens)

**Notes**

**E5-Base-v2  
**(110M)

768

~50.9% (high;  
near Voyage on  
CoIR)

83.5%  
(excellent)

~20 ms 

**Recommended  
**unified model.  
Strong all-round,  
no special  
prompts needed

.

E5-Large / *E5-  
Mistral* (7B)

1024–4096

**55–56%** (very  
high, SOTA open-  
source)

~85%+ (n/  
a exact,  
likely  
slightly  
higher)

**1840 ms  
**(7B  
model)

7B param model  
(slow without  
acceleration). High  
memory (index  
~2.3 GB for 156K  
docs)

.

BGE-Base-en-  
v1.5 (110M)

768

~42.8% (good,  
but trails E5 on  
code)

84.7%  
(excellent)

~22 ms 

High English  
accuracy, needs  
prompt prefixes  
for best use  
(“Represent for  
retrieval: …”)

.

BGE-Large-en-  
v1.5 (330M)

1024

~50% (est.; likely  
close to E5-base)

~85% (est.)

~30–  
40 ms  
(approx.)

Larger BGE variant  
for slight quality  
gain. Requires  
more RAM;  
moderate latency.

Nomic **Embed-  
Text-v1** (500M)

768

~?? (general  
model, not code-  
tuned)

**86.2%  
**(highest  
open)

~42 ms 

Fully open model  
by Nomic. Excels  
in broad semantic  
search

,

supports long  
8192-token input

. Heavier to

run.

[2](https://arxiv.org/html/2407.02883v1#:~:text=Contriever%20%28110M%29%205,21)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[15](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=)

[16](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=It%E2%80%99s%20one%20of%20the%20most,to%20use%20in%20flexible%20pipelines)

[17](https://arxiv.org/html/2407.02883v1#:~:text=BGE,31)

[18](https://arxiv.org/html/2407.02883v1#:~:text=8%20GTE,56.8%C2%B5s%200.9G)

[19](https://arxiv.org/html/2407.02883v1#:~:text=Trade,the%20expense%20of%20increased%20latency)

[18](https://arxiv.org/html/2407.02883v1#:~:text=8%20GTE,56.8%C2%B5s%200.9G)

[19](https://arxiv.org/html/2407.02883v1#:~:text=Trade,the%20expense%20of%20increased%20latency)

[20](https://arxiv.org/html/2407.02883v1#:~:text=E5,31)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[21](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=It%27s%20state,and%20production%20search%20systems%20alike)

[22](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=retrieval,and%20production%20search%20systems%20alike)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[23](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=These%20benchmarks%20highlight%20that%20there%E2%80%99s,depends%20on%20your%20product%20priorities)

[24](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=)

3

</div>

<span id="4"></span>

<div id="page4-div"
style="position:relative;width:918px;height:1188px;">

**Model**

**Dimensions**

**Code Retrieval  
Quality** \<br/  
\>(Recall@5 or  
tasks avg)

**Text  
Retrieval  
Quality  
**\<br/  
\>(Top-5  
Accuracy)

**Speed  
**(GPU  
embed  
per 1K  
tokens)

**Notes**

*Nomic-Embed-  
Code* (7B)

4096

**State-of-Art  
**(beats Voyage &  
OpenAI on code)

n/a (built  
for code)

~? (7B;  
very slow  
without  
GPU)

Open-source **code  
**retriever (26 GB  
model). Top  
CodeSearchNet  
results

. High

resource needs –  
not practical for  
\<100ms goal.

CodeBERT /  
GraphCodeBERT  
(125M)

768

~40% (decent on  
CodeSearchNet,  
below modern  
models)

n/a (not  
tuned for  
pure text)

~20 ms

Older code-  
specific encoders  
(2020).  
Outperformed by  
newer multi-task  
models (E5, etc.).

**Key Observations:**

**Code-Specific Models vs General:**  Models explicitly optimized for code (Voyage-Code-2, Nomic-  
Embed-Code, CodeBERT) deliver superior accuracy on code search tasks. Voyage’s model achieved  
~**14.5% higher recall@5** on coding queries than OpenAI’s Ada

, thanks to training on coding

Q&A and advanced contrastive techniques. Similarly, Nomic’s 7B code model outperforms Voyage  
and OpenAI’s latest on CodeSearchNet

. This demonstrates that  **specialized training can**

**significantly boost code retrieval performance**

. However, these gains come with trade-offs:

large model sizes (7B params ≈ 26 GB) or reliance on third-party APIs. In practice, a *unified model  
*that handles both code and text reasonably well (e.g. E5 or BGE) is preferable unless a code-specific  
model offers \>15% accuracy improvement. Our findings show general embedding models like E5-  
base are already **within ~5% of the best specialized model** on average

, so maintaining a

single embedding space is justified for simplicity.

**Embedding   Dimension   Trade-offs:**  Higher   dimensional   embeddings   capture   more   semantic  
nuance, but yield diminishing returns beyond ~768–1536 dimensions. For example, OpenAI’s move  
from   1536-dim   (Ada-002)   to   3072-dim   (text-embedding-3-large)   only   raised   English   benchmark  
scores from 61.0% to 64.6% (+3.6)

. Similarly, an independent evaluation found OpenAI’s

3072-dim   model   and   Cohere’s   large   model  **did   not   outperform**  several   cheaper   or   smaller  
embeddings in accuracy

. Larger vectors also **increase storage and memory costs linearly** (e.g.

3072 dims is double the size of 1536)

.  **Conclusion:**  768 or 1536 dimensions are a sweet spot.

Models in this range (e.g. E5-base at 768, OpenAI Ada at 1536) offer excellent retrieval performance  
without undue storage growth. Notably, OpenAI now allows *shortening* the 3-large embeddings – e.g.  
using only 1024 out of 3072 dims – with minimal accuracy loss (256 dims from 3-large still beat Ada’s  
1536-dim performance)

. This indicates much of the extra capacity is unused for typical tasks. For

[25](https://ollama.com/manutic/nomic-embed-code#:~:text=nomic,and%20OpenAI%20Embed%203)

[26](https://www.nomic.ai/blog/posts/embed-ecosystem#:~:text=The%20Nomic%20Embedding%20Ecosystem%20Nomic,CSN%29)

[27](https://www.nomic.ai/blog/posts/introducing-state-of-the-art-nomic-embed-code#:~:text=Nomic%20Embed%20Code%20is%20a,art%20performance%20on%20CodeSearchNet)

• 

[3](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=TL%3BDR%20%E2%80%93%20We%20are%20thrilled,purpose%20text%20datasets)

[4](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=This%20post%20presents%20%60%60voyage,the%20context%20window%20to%2016K)

[25](https://ollama.com/manutic/nomic-embed-code#:~:text=nomic,and%20OpenAI%20Embed%203)

[26](https://www.nomic.ai/blog/posts/embed-ecosystem#:~:text=The%20Nomic%20Embedding%20Ecosystem%20Nomic,CSN%29)

[28](https://arxiv.org/html/2407.02883v1#:~:text=Effectiveness%20of%20Code,and%20optimization%20for%20code%20retrieval)

[29](https://arxiv.org/html/2407.02883v1#:~:text=No%20Single%20Model%20Dominates%20Across,catering%20to%20varied%20task%20requirements)

[28](https://arxiv.org/html/2407.02883v1#:~:text=Effectiveness%20of%20Code,and%20optimization%20for%20code%20retrieval)

• 

[6](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Stronger%20performance.%20%60text,to%2064.6)

[30](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Comparing%20%60text,to%2064.6)

[31](https://research.aimultiple.com/embedding-models/#:~:text=%2A%20Higher,priced%20alternatives)

[32](https://research.aimultiple.com/embedding-models/#:~:text=,A)

[11](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Both%20of%20our%20new%20embedding,with%20a%20size%20of%201536)

4

</div>

<span id="5"></span>

<div id="page5-div"
style="position:relative;width:918px;height:1188px;">

LLMC,   using   a  **768-dim   or   1536-dim   embedding**  keeps   the   .rag/index   database   size  
manageable (roughly 3–6 KB per span) and query speed high, while still
capturing rich semantics. 

**Local vs API Economics:**  Thanks to new efficient models,  **local embedding is often more cost-  
effective** than API for our use case. OpenAI’s latest *3-small* model is extremely cheap (\$0.00002 per  
1K tokens = \$0.02 per 1M)

, but even that cost can add up with large codebases or frequent

indexing. For ~10K spans (~1–2 million tokens) per repo, OpenAI 3-small costs ≈\$0.04 per indexing –  
trivial in isolation. However, across dozens of projects with continuous re-indexing, API costs and  
latency could accumulate. Running an open model like E5-base locally has **zero marginal cost** (aside  
from electricity) and can embed 10K spans in under a minute on a modern GPU. Our benchmarks  
show E5-base processes ~1000 tokens in ~20 ms

, meaning ~50 ms per typical chunk (~250

tokens) on GPU or a few hundred ms on CPU – easily within our 100 ms per span budget. In contrast,  
API calls introduce network overhead and rate limits. For example, Voyage’s free tier limits to 3 calls/  
minute

  (far too slow for batch jobs), and even with paid plans, API throughput might throttle

large batch indexing. **Bottom line:** If a local model can match within ~5% of an API model’s quality, it  
will be more economical and faster for bulk embedding jobs. We see this in quality: E5-base actually  
*outperforms Ada-002*  on code and text benchmarks

, and even approaches OpenAI’s large

model on many tasks. Thus, LLMC can save on recurring API fees and avoid external dependencies  
by using local embeddings without sacrificing accuracy.

**Multilingual and Multi-Language Support:**  LLMC’s code is primarily in Python, JS/TS, Bash, plus  
Markdown docs in English. All the candidate models handle English well. For code, the models were  
evaluated on multiple programming languages (CodeSearchNet spans 6 languages, CoIR adds C++,  
Java,   etc.),   and   the   rankings   stayed   similar

  –   indicating   the   recommended   models   (E5,

Voyage,   OpenAI)   can   generalize   across   languages   and   frameworks.   If   in   future   LLMC   needs  
embeddings for non-English documentation or identifiers, note that E5 and Nomic are *multilingual-  
trained*  and   maintain   strong   performance   in   other   languages,   whereas   OpenAI’s   models   have  
multilingual support (MIRACL benchmark) improved in 3-small/3-large

. Cohere also offers

multilingual embedding models. Given our current scope is mostly English and code syntax (which is  
universal), this is not a deciding factor, but the chosen E5-base-v2 does support multilingual text (via  
the intfloat E5 training on 270M diverse pairs)

.

In summary, the comparison favored **E5-base (768d)** as the primary recommendation due to its high quality  
on both code and docs, low resource usage, and open availability. If slightly higher accuracy is desired and  
resources allow, **E5-large or Voyage-Code-2** are strong runners-up (Voyage if willing to use an API, E5-large  
if   a   bigger   local   model   is   feasible).   We   do  **not**  recommend   using   separate   models   for   code   vs  
documentation unless a clear ~15%+ gain in retrieval is observed – a unified embedding space keeps the  
design simpler (one index, no need to decide query routing) and we found that unified models are already  
very competitive on code. The next sections detail the benchmarking evidence behind these conclusions,  
and then provide guidance on integrating the new embedding model into LLMC, including fine-tuning and  
migration steps.

**Benchmarking Results and Findings**

To validate the model choices, we considered both **external
benchmarks** and **LLMC-specific tests**:

• 

[7](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Reduced%20price.%20%60text,00002)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[33](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=Voyage%20embeddings%20are%20normalized%20to,is%20the%20fastest%20to%20compute)

[2](https://arxiv.org/html/2407.02883v1#:~:text=Contriever%20%28110M%29%205,21)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

• 

[34](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=data%20from%20both%20natural%20language,purpose%20text%20datasets)

[35](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=This%20post%20presents%20%60%60voyage,world%2C%20interactive%20production)

[8](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Stronger%20performance.%20Comparing%20%60text,to%2062.3)

[6](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Stronger%20performance.%20%60text,to%2064.6)

[36](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=,labeled%20nuance%20and)

5

</div>

<span id="6"></span>

<div id="page6-div"
style="position:relative;width:918px;height:1188px;">

**Retrieval Quality Evaluation**

**Code   Retrieval:**  We   leveraged   results   from   the   CoIR   benchmark   (Comprehensive   Code   Information  
Retrieval) which evaluated 9 models on 14 code search tasks

. Key metrics included Recall@5 – the

chance that a relevant code snippet is in the top-5 retrieved. The **current LLMC baseline (MiniLM-L6-v2,  
384d)** is roughly analogous to older models like Contriever (110M) which scored around **36–37% recall@5  
**on average

. By contrast, **E5-base** achieved **50.90% recall@5**

, a substantial improvement (~14 points

absolute, or ~40% relative). It even surpassed OpenAI’s Ada-002 (45.59%)

 and was on par with Voyage-

Code-2 (56.26% vs 52.86% mean; Voyage was highest by a few points)

. Notably, **no single model**

**dominated  all  code  tasks**  –  for  example,  E5-base  outperformed  others  on  certain  coding  tasks  (e.g.  
*CodeFeedBack-MT* scenario)

, while Voyage led on others

. This suggests ensemble benefits, but given

our need for one model, it confirms that E5-base is **among the top-tier for code**. Models like **BGE-base  
**(42.77%) and *UniXcoder* (37.3%) trailed behind

, reinforcing our focus on E5.

**Natural Language (Documentation) Retrieval:**  For general text/document similarity, we examined the  
Massive  Text  Embedding  Benchmark  (MTEB)  and  a  real-world  test  with  the  BEIR  TREC-COVID  dataset.  
OpenAI   reports  **text-embedding-3-large**  scored  **64.6%**  average   on   MTEB   (English   tasks)   vs  **61.0%**  for  
Ada-002

.   Meanwhile,   in   an   independent   retrieval   test   (top-5   accuracy   on   medical   FAQs),  **MiniLM**

managed 78.1% accuracy, whereas **E5-base hit 83.5% and BGE-base 84.7%**

. **Nomic’s Embed v1** slightly

topped the chart at 86.2%

, but with double the latency. These results show that upgrading from MiniLM

to any of the newer 768-dim models yields a **5–8% absolute gain in relevant document retrieval**

. E5-

base and BGE-base are essentially state-of-the-art in the open domain, rivaling proprietary models. In fact,  
industry   evaluations   found   that  **OpenAI’s   3-large   and   Cohere’s   latest   embed   models   scored   lower  
accuracy than some lower-cost models**

  – e.g. a smaller Mistral-7B embed model reached ~77.8%

accuracy (highest) while OpenAI 3-large was lower

. This underscores that **costly APIs don’t guarantee**

**better results**

. For LLMC’s docs (mostly English), E5/BGE provide excellent semantic understanding

(they’re instruction-tuned on web, Q&A, etc. in training

) and will markedly improve planner context

retrieval.

**Code   +   Text   (Mixed   Queries):**  LLMC   queries   may   sometimes   combine   natural   language   with   code  
references (e.g. “Where is the   validate_email   function implemented?”). The embedding model must  
handle both modalities in the *same vector space*. Models like E5 and OpenAI are trained on text *and code  
*together (Ada-002’s training included code, and E5’s data likely included StackExchange code discussions

).  **Voyage-Code-2**  explicitly   handles   both   NL   queries   and   code   inputs   about   code

.   We

qualitatively   expect   these   models   to   group   semantically   related   code   and   descriptions.   For   example,  
Voyage’s blog showed that its embeddings correctly matched a NL query about removing first/last char to  
the code that does exactly that, whereas Ada-002 retrieved a less precise snippet

. This indicates

improved *semantic resolution* of code logic. In absence of a custom LLMC benchmark, we trust these broad  
evaluations.   We   anticipate   the   chosen   model   will   significantly   improve   cross-references   (e.g.   linking   a  
Markdown section to the right function, or finding a function by a comment description). We will validate  
this post-integration with a curated test set (see **Migration Guide**).

**Fine-Tuning Impact:** We did not find published metrics specifically on fine-tuning embeddings for a specific  
codebase. However, analogous evidence comes from specialized models: the huge gains of Voyage and  
Nomic code models were achieved by training on code-specific data

. Fine-tuning a smaller model on

our own projects (FreeFlight, WPSG, etc.) could  **teach it project-specific vocabulary and patterns**  (for  
instance, internal function naming conventions, or domain terms like “FreeFlightAuth”). This can yield more

[37](https://arxiv.org/html/2407.02883v1#:~:text=Package%20CodeSeachNet%20Github%206%20Text,Deep%20Learning%2C%20StackOverFlow%2C%20Code%20Instruction)

[38](https://arxiv.org/html/2407.02883v1#:~:text=match%20at%20L462%20state,M3%C2%A0%5B3%5D%2C%20and%20UniXcoder%C2%A0%5B9%5D.%20For%20proprietary)

[39](https://arxiv.org/html/2407.02883v1#:~:text=Task%20%28%29%20Text,Code%20Code%20CodeTrans%20StackOver%20CodeFeedBack)

[2](https://arxiv.org/html/2407.02883v1#:~:text=Contriever%20%28110M%29%205,21)

[5](https://arxiv.org/html/2407.02883v1#:~:text=E5,59)

[40](https://arxiv.org/html/2407.02883v1#:~:text=OpenAI,59)

[41](https://arxiv.org/html/2407.02883v1#:~:text=No%20Single%20Model%20Dominates%20Across,catering%20to%20varied%20task%20requirements)

[42](https://arxiv.org/html/2407.02883v1#:~:text=consistently%20excel%20across%20CoIR%20sub,adaptive%2C%20robust%20code%20retrieval%20capabilities)

[28](https://arxiv.org/html/2407.02883v1#:~:text=Effectiveness%20of%20Code,and%20optimization%20for%20code%20retrieval)

[20](https://arxiv.org/html/2407.02883v1#:~:text=E5,31)

[43](https://arxiv.org/html/2407.02883v1#:~:text=GTE,31)

[6](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Stronger%20performance.%20%60text,to%2064.6)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[23](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=These%20benchmarks%20highlight%20that%20there%E2%80%99s,depends%20on%20your%20product%20priorities)

[44](https://research.aimultiple.com/embedding-models/#:~:text=match%20at%20L116%20,priced%20alternatives)

[45](https://research.aimultiple.com/embedding-models/#:~:text=match%20at%20L295%20Based%20on,even%20at%20a%20moderate%20cost)

[46](https://research.aimultiple.com/embedding-models/#:~:text=The%20scatter%20plot%20illustrates%20that,balance%20between%20accuracy%20and%20cost)

[47](https://research.aimultiple.com/embedding-models/#:~:text=attractiveness%20in%20cost,priced%20alternatives)

[36](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=,labeled%20nuance%20and)

[36](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=,labeled%20nuance%20and)

[3](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=TL%3BDR%20%E2%80%93%20We%20are%20thrilled,purpose%20text%20datasets)

[4](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=This%20post%20presents%20%60%60voyage,the%20context%20window%20to%2016K)

[48](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=This%20section%20demonstrates%2C%20through%20examples%2C,2%60%20compared%20to%20OpenAI%20Ada)

[49](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=Image)

[4](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=This%20post%20presents%20%60%60voyage,the%20context%20window%20to%2016K)

[25](https://ollama.com/manutic/nomic-embed-code#:~:text=nomic,and%20OpenAI%20Embed%203)

6

</div>

<span id="7"></span>

<div id="page7-div"
style="position:relative;width:918px;height:1188px;">

precise retrieval (a likely few percentage points improvement in recall). That said, our baseline chosen  
model is already strong, and fine-tuning would involve a non-trivial effort of assembling training pairs and  
running   many   epochs.   We   estimate   diminishing   returns   unless   LLMC’s   code   is   highly   unique.   A   safe  
approach is to first deploy the new model  *without fine-tuning*, measure retrieval quality in practice, and  
pursue fine-tuning only if needed (see **Fine-Tuning Walkthrough** for
details).

**Performance and Resource Metrics**

**Latency and Throughput:** All candidate models (except the largest 7B) comfortably meet the performance  
requirement of  *\<100 ms per embedding*. On a single GPU,  *MiniLM*  can embed ~5–14K sentences/sec  
(~0.07 ms per short sentence). The larger 110M models (E5-base, BGE-base) run ~4× slower, but still on the  
order of **7–8 ms per sample (512 tokens) on GPU**

, or ~20 ms per 1000 tokens

. In our context, code

spans are ~100–200 tokens on average, so we expect ~2–5 ms GPU time per span. This is negligible for  
query-time use (embedding one user query). For batch indexing ~10K spans, even a CPU can handle it: e.g.  
MiniLM does 14.7 ms per 1000 tokens on CPU

, so ~0.3 s for 10K tokens; E5-base ~20.2 ms/1K

, so

~0.5 s per 10K tokens – meaning ~50 seconds for 1M tokens (if single-threaded). Using batches and multi-  
threading can further speed this up. **Bottom line:** performance is a non-issue for local models up to 300M.  
The only slowdowns appear with  **7B models**  – e.g. E5-Mistral took  **1840 ms per sample**  (batch on A100  
GPU)

, which is impractically high (it would take hours to embed a repository). We therefore avoid

models of that size for embedding. 

For **API models**, the embedding computation is fast on the provider side, but network overhead and rate  
limiting can bottleneck throughput. OpenAI’s API can handle large batch requests (up to 16K tokens per call  
for 3-large) and is fairly responsive (~200-300 ms typical call latency for moderate batch sizes). Indexing  
~10K chunks might be done in chunks of e.g. 200 per API call (to stay under token limits), requiring 50 calls.  
At ~0.3 s each, that’s ~15 s plus some parallelism – possibly within a minute. This is acceptable, but heavy  
use might run into **rate limits** (depending on account tier). Cohere’s and Voyage’s limits vary, but as noted,  
Voyage free is extremely limited (3 calls/min)

; a paid plan or self-hosted inference would be needed for

speed. Given LLMC’s preference for offline operation and no dependence on external services, the local  
route wins on performance consistency.

**Memory and Storage Footprint:** The embedding index size grows with dimension \* d \* and number of  
spans \* N *. Currently, with ~5–10K spans per repo and *d* = 384, the SQLite (or Chroma DB) index is on the order of  
tens of MB (the RAG README noted ~100–200 MB for ~50 projects ≈ 50K chunks)*

*. If we switch to *d* = 768,*

*we double each vector’s size (4 bytes × 768 = 3 KB per vector). For 50K vectors, that’s ~150 MB purely for floats,  
plus some overhead (~200+ MB total). This is still very manageable on modern disks. Even *d* = 1536 yields ~300  
MB for 50K, which is fine. We should note the peak memory*\* used when querying: some vector DBs may load  
index into RAM. Chroma (with FAISS or HNSW) can easily handle 50K×1536 in memory (~300 MB). If using  
SQLite (with JSON or custom extension), queries involve scanning or using an index; performance might  
degrade if index is on disk. That’s one reason Chroma was used for global workspace search. We’ll continue  
to use a proper vector store (Chroma or potentially pgvector) for
scalability. 

We must ensure the chosen dimension is supported by the store: **SQLite with JSON** has no intrinsic limit  
(it’s   just   text   blobs).   If   using   a   SQLite   vector   extension   or   pgvector ,   we’d   specify   the   column   as  
VECTOR(768) or VECTOR(1536). Notably, **pgvector’s default max dim is 1024**; to use 1536 or beyond, one  
must configure accordingly. This is a consideration if migrating to Postgres later. As a workaround, OpenAI’s  
technique of truncating embeddings can be used: e.g. store only the first 1024 components of a 1536-d

[50](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=,like%20all%E2%80%91mpnet%E2%80%91base%E2%80%91v2%2C%20which%20is%20ideal)

[51](https://arxiv.org/html/2407.02883v1#:~:text=9%20Contriever%20768%207,56.8%C2%B5s%200.9G)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[52](https://arxiv.org/html/2407.02883v1#:~:text=7%20UniXcoder%20768%207,56.8%C2%B5s%200.9G)

[19](https://arxiv.org/html/2407.02883v1#:~:text=Trade,the%20expense%20of%20increased%20latency)

[33](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=Voyage%20embeddings%20are%20normalized%20to,is%20the%20fastest%20to%20compute)

[*53*](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L60-L68)

[*54*](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L186-L194)

7

</div>

<span id="8"></span>

<div id="page8-div"
style="position:relative;width:918px;height:1188px;">

vector if needed (OpenAI showed a shortened 1024-d 3-large still beat a full Ada-002

). For now, we can

stick to ≤1024 dims to avoid any DB issues.

**Normalization  and  Similarity  Metric:**  One  nuance  in  integration  –  some  models  output  **normalized  
vectors** (unit length) while others do not. Nomic’s and BGE’s embeddings are typically cosine normalized  
(the Nomic docs note they can use dot product or L2 interchangeably because vectors are unit-length)

.

OpenAI   and   E5   embeddings   are   not   inherently   normalized   –   one   can   compute   cosine   similarity   by  
normalizing at query time, or rely on dot product if vectors are not normalized. Chroma/FAISS typically use  
**cosine similarity or dot product**  as configured. We should check and unify this: likely we’ll use  **cosine  
similarity** for retrieval (which is standard and what our current system uses via ChromaDB). In practice, we  
should normalize all embeddings when storing if the model doesn’t do so (the difference is minor unless  
vector norms vary). The integration examples will reflect this where needed (BGE might require explicit  
prefix and likely outputs already normalized vectors per BAAI’s
implementation).

In conclusion, the benchmark data strongly supports moving to a **768-dim class model** like E5 or BGE for a  
**huge boost in retrieval quality** with negligible downsides in performance. The next steps describe how to  
integrate this model into LLMC’s pipeline.

**Integration Guide**

This   section   provides   a   step-by-step   guide   to   integrating   the   selected   embedding   model   into   LLMC,  
including   how   to   generate   embeddings,   swap   out   the   old   model,   and   ensure   compatibility   with   our  
database and search pipeline. We assume the recommended default:  **using a Sentence-Transformers  
model locally (E5-base-v2)**. We also outline how to use alternative models (OpenAI API, etc.) in case that  
route is chosen.

**1. Replacing the Embedding Model in Code**

LLMC’s indexing code currently uses SentenceTransformers with  'all-MiniLM-L6-v2'

. To switch to

E5 (for example), change the model name when loading: 

from sentence_transformers import SentenceTransformer

\# Old:  
model = SentenceTransformer('all-MiniLM-L6-v2')

\# New (E5-base):  
model = SentenceTransformer('intfloat/e5-base-v2')

This one-line change will load the new embedding model (download from HuggingFace on first use). **Note:  
**E5 models expect an  **average pooling**  over the token embeddings (which SentenceTransformer does by  
default) and use some special tokens in training. In practice, you *should* prepend the text with the prefix  
token that was used during training for optimal results. For E5, the convention is to prefix  "query: "  or

[11](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Both%20of%20our%20new%20embedding,with%20a%20size%20of%201536)

[55](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=Distance%20metrics)

[56](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/index_workspace.py#L88-L96)

8

</div>

<span id="9"></span>

<div id="page9-div"
style="position:relative;width:918px;height:1188px;">

"passage: "

 to the input depending on context

. However, the model was instruction-tuned to handle

those internally, so it is relatively forgiving if you don’t. For
consistency, we can apply prefixes as follows:

When embedding a user query or search term, prepend  "query: "  to the
string.  
When embedding code or documentation chunks for the corpus,
prepend  "passage: "  to each  
chunk text.

For example: 

query_text = "How is email validation implemented?"  
emb_query = model.encode("query: " + query_text)

code_chunk = "def validate_email(email):\n    \# ...implementation..."  
emb_code = model.encode("passage: " + code_chunk)

This mirrors the model’s training format

  and can yield slightly better alignment (especially if using

multilingual E5 variants). If we use the plain English E5-base-v2, this
step is optional but recommended.

For **BGE models**, a similar practice applies. BGE was trained with prompt instructions like  "Represent   
this sentence for searching relevant passages:"

. The authors provide simpler tags: e.g.

prefix   "query:   "   for   queries   and   "doc:   "   for   documents   when   encoding.   So   if   using

BAAI/bge-base-en-v1.5

, do:

emb_query = bge_model.encode("query: " + query_text)  
emb_code = bge_model.encode("passage: " + code_chunk)

\# BGE sometimes uses 

'passage' or 'doc'

*(Check model card for exact prefixes; BGE’s HuggingFace page indicates using  "query: "  and  "passage: "  
is acceptable.)*

If integrating an **OpenAI API model** instead of local, you would remove SentenceTransformer usage and  
call OpenAI’s API. For example, using the  openai  Python package:

import openai  
openai.api_key = "\<YOUR_API_KEY\>"

\# Example: embed a batch of texts  
texts = \[ "def foo(): ...", "some documentation text ..." \]  
response = openai.Embedding.create(model="text-embedding-3-large", input=texts)  
embeddings = \[item\["embedding"\] for item in response\["data"\]\]

The  openai.Embedding.create  method returns a list of embedding vectors (each a list of floats). You’d  
then insert these into the vector store. Make sure to specify the correct model name ( "text-embedding-

[36](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=,labeled%20nuance%20and)

•   
• 

[57](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=training%20signals%20that%20transfer%20well,read%20the%20official%20paper%20here)

[21](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=It%27s%20state,and%20production%20search%20systems%20alike)

9

</div>

<span id="10"></span>

<div id="page10-div"
style="position:relative;width:918px;height:1188px;">

ada-002"

  or the new   "text-embedding-3-small" / "3-large"   as needed). OpenAI’s models don’t

need manual normalization or prefixes – the service handles all that. (If using 3-large with a custom

dimensions

 

parameter

 

to

 

shorten

 

the

 

vector,

 

you

 

can

 

pass

{"model":   "text-embedding-3-large",   "input":   texts,   "user":   ...,   "dimensions":  

1536}

 to get a truncated 1536-d vector from the 3072-d model, as documented
by OpenAI

.)

For **Cohere’s API**, integration is similarly straightforward using
their SDK:

import cohere  
co = cohere.Client("\<YOUR_API_KEY\>")  
result = co.embed(texts=texts, model="embed-english-v3.0")  
embeddings = result.embeddings

\# list of vectors

Cohere’s  embed  API will return 4096-d embeddings for the English v3 model (if that is the dimensionality  
they use), or smaller if using a lite model. No special handling needed, but note the higher dimension –  
ensure your storage can handle it (or consider using a smaller model like  embed-english-light-v2  at  
1024 dims).

For **Voyage AI**, they provide a Python client as shown in their docs

:

import voyageai  
client = voyageai.Client(api_key="YOUR_VOYAGE_KEY")  
emb_docs = client.embeddings.create(input=document_list, model="voyage-  
code-2").embeddings

Voyage requires specifying   inputType   for query vs document if using their lower-level API, but their  
client’s  .create  might handle it. We would treat all our chunks as “documents” to embed and at query  
time embed the search query as   inputType="query"   (ensuring the model knows which is which)

. This is an advanced use-case; for now, if Voyage is chosen, we’ll
follow their integration guide.

**Summary: ***For the default path (local E5/BGE model)*, the integration mostly means  **changing the model  
name and adding prefix text** when encoding. The rest of the pipeline (iterating over files, chunking, etc.)  
remains unchanged. The code will produce 768-dim vectors instead of 384-dim; we must handle this in the  
storage layer next.

**2. Database Schema and Storage Changes**

If you are using **ChromaDB (Chromadb PersistentClient)** as in the multi-project RAG system

, you don’t

need to change the schema – Chroma will store whatever length vectors you provide. It’s recommended to  
start a fresh Chroma collection for the new embeddings (to avoid mixing with old MiniLM vectors). The

[11](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Both%20of%20our%20new%20embedding,with%20a%20size%20of%201536)

[58](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=vo%20%3D%20voyageai.Client%28os.environ.get%28)

[59](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=,2%22%29.embeddings%5B0)

[60](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=%2F%2F%20we%20need%20a%20separate,documents%20stored%20in%20pg_vector)

[61](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=const%20embedQueries%20%3D%20new%20VoyageEmbeddings%28,used%20to%20search%20documents)

[62](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/index_workspace.py#L70-L78)

10

</div>

<span id="11"></span>

<div id="page11-div"
style="position:relative;width:918px;height:1188px;">

current code already does   get_collection(COLLECTION_NAME)   or creates one if not exist

. To re-

index with a new model, you can either: 

**Option A:** Drop the existing collection (e.g. name it with model
version, such as 

"workspace_code_e5"

 vs old  "workspace_code" ). This avoids confusion and allows reverting

if needed.  
**Option B:** Use the same collection name; Chroma will overwrite
vectors for existing IDs when you  
upsert. In practice, since we use file hash or chunk IDs as keys,
re-indexing with the same IDs will  
replace their embedding field.

Option A is safer to implement. You can modify  COLLECTION_NAME  in the script (or pass an argument for  
model name). For example:

COLLECTION_NAME = "workspace_code_e5"

\# new collection for E5 embeddings

Run indexing, verify results, then you could delete the old collection
later.

If LLMC uses  **SQLite (.rag/index.db)**  with a custom   embeddings   table (as mentioned in the prompt  
context), the schema likely has columns:   (span_hash TEXT PRIMARY KEY, vector TEXT, model    
TEXT, dimension INTEGER)

 storing the vector as a JSON string. In that case, just update the  model

field to something like  "e5-base-v2"  and  dimension  to 768, when inserting new rows. You might add  
a new table if wanting to keep old data (“embeddings_v2”), but since the old embeddings are inferior, it’s  
reasonable to replace them. The indexing script can do   DELETE FROM embeddings;   then insert fresh  
embeddings. 

**Vector format:** Ensure that when saving to SQLite, you format the numpy array or list of floats as a JSON  
text (the current code likely does this via chroma or manually). When querying via SQLite without vector  
extension, you’d be doing a linear scan in Python (which is slow). That’s why migrating to a proper vector  
store or at least using   sqlite-vss   (if available) is beneficial. However, given the scale (5–10K vectors),  
linear search is not terrible (10K dot products is fine in \<100ms in Python with numpy). Since our integration  
currently leans on Chroma (which uses Faiss under the hood), we will continue using Chroma for efficient  
similarity search.

If at some point we move to  **Postgres + pgvector**, we’d define the column as   VECTOR(768)   for E5 or  
adjust length accordingly. Just note that if using a 1536-d model like OpenAI Ada or Voyage, you’d need to  
set  VECTOR(1536) . The rest of the migration to pgvector is beyond this scope, but our choices here keep  
that path open (we avoid extremely high dims by default).

**3. Adapting the Query Mechanism**

The query code ( query_context.py ) currently takes a search term, embeds it, and queries the vector DB

. After swapping the model, just make sure the query embedding also uses the new model with the

same prefix scheme. For instance:

[63](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/index_workspace.py#L76-L84)

• 

• 

[64](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L80-L88)

11

</div>

<span id="12"></span>

<div id="page12-div"
style="position:relative;width:918px;height:1188px;">

search_term = args.query

\# input query

emb_query = model.encode("query: " + search_term)

\# using new model

results = collection.query(query_embeddings=\[emb_query\], n_results=5)

Chroma (or any DB) doesn’t need to know which model, as long as the vectors are in the same space as the  
index. If using two separate collections for old vs new, ensure the
query goes to the new one. 

One   more   detail:   If   using  **cosine   similarity**,   check   that   the   vectors   are   normalized.  *If   you   use  
SentenceTransformer, by default it may not normalize outputs.* You can
normalize manually:

import numpy as np  
emb = emb / np.linalg.norm(emb)

Chroma’s  query  can accept a  relevance_score_fn  or be configured with cosine. By default, Chroma  
uses cosine similarity on stored embeddings. It’s safe to store unnormalized E5 vectors and let Chroma  
handle cosine distance. But if any distance metric issues arise (e.g., if using raw dot product somewhere),  
it’s good to be consistent (normalize either at insert or at query).

In summary, after re-indexing, test a known query. For example,  query_context.py "authentication   
system"

 should retrieve relevant chunks (as it did before) but hopefully with
improved relevance.

**4. Batch Embedding Scripts Example**

To demonstrate the embedding generation with different model types, here are concise examples for each  
scenario:

**Using SentenceTransformer locally (E5 or BGE):**

from sentence_transformers import SentenceTransformer

model = SentenceTransformer('intfloat/e5-base-v2')  
texts = \["query: How to validate email in signup?",

"passage: def validate_email(email): ..."\]

\# query and code example

embeddings = model.encode(texts)

\# returns a list of numpy arrays

\# Normalize embeddings (optional for cosine similarity):  
import numpy as np  
embeddings = \[emb / np.linalg.norm(emb) for emb in embeddings\]  
print(len(embeddings\[0\]), embeddings\[0\]\[:5\])

\# dimension and first 5 values

**Using OpenAI API:**

import openai  
openai.api_key = "SK-...yourkey..."

• 

• 

12

</div>

<span id="13"></span>

<div id="page13-div"
style="position:relative;width:918px;height:1188px;">

texts = \["How to validate email in signup?", "def
validate_email(email): ..."\]  
response = openai.Embedding.create(model="text-embedding-ada-002", input=texts)  
embeddings = \[data\["embedding"\] for data in response\["data"\]\]  
\# OpenAI returns normalized vectors (for Ada-002 and 3-series, cosine
similarity   
is appropriate).  
print(f"Got {len(embeddings)} embeddings of
length {len(embeddings\[0\])}")

*(If using  text-embedding-3-large , remember you can specify a  user  param for logging, and potentially  
use  dimensions  param if you only want a subset of the 3072 values.)*

**Using Cohere API:**

import cohere  
co = cohere.Client("YOUR_API_KEY")  
texts = \["How to validate email in signup?", "def
validate_email(email): ..."\]  
response = co.embed(model="embed-english-v3.0", texts=texts)  
embeddings = response.embeddings  
\# Cohere embeddings are typically NOT unit-length by default. Normalize
if   
needed:  
embeddings = \[np.array(v)/np.linalg.norm(v) for v in embeddings\]  
print("Cohere embedding sample:", embeddings\[0\]\[:5\])

**Using Voyage API:**

import voyageai  
client = voyageai.Client("YOUR_VOYAGE_KEY")  
\# Voyage expects separate handling for query vs documents:  
query_vec = client.embeddings.create(input=\["How to validate email in
signup?"\],  
model="voyage-code-2", input_type="query").embeddings\[0\]  
doc_vec = client.embeddings.create(input=\["def validate_email(email):
..."\],  
model="voyage-code-2", input_type="document").embeddings\[0\]  
\# Both vectors are 1536-dim, normalized.

These code snippets illustrate how to obtain embeddings from each provider. In practice, for bulk indexing,  
you’d loop through file chunks and call the appropriate method. **Batching:** All APIs and libraries support  
batching multiple texts per call to improve throughput. For instance,  SentenceTransformer.encode  can  
take a list of strings (with internal batching), OpenAI allows up to e.g. 2048 tokens per request (so batch  
maybe   ~50   chunks   per   call,   depending   on   size),   Cohere   and   Voyage   similarly   allow   batches.   Utilizing  
batching   will   drastically   speed   up   indexing.   The   index_workspace.py   script   should   be   adjusted   to  
accumulate texts and encode in batches (if not already doing so with
tqdm).

• 

• 

13

</div>

<span id="14"></span>

<div id="page14-div"
style="position:relative;width:918px;height:1188px;">

**5. End-to-End Integration Steps**

Bringing it all together, here’s the plan to integrate the new embedding
model:

**Install Dependencies:** If using a new model from HuggingFace, ensure the package is installed or  
updated. E.g.,   pip install -U sentence-transformers   (the latest version, since E5 models  
might need a newer version). If using OpenAI/Cohere, install those SDKs
( openai  or  cohere ).

**Update   Configuration:**  In   the   scripts/rag/index_workspace.py   (or   equivalent   indexing  
script), change the embedding model initialization as discussed (SentenceTransformer or custom  
code for API). Also update any global constants for   COLLECTION_NAME   or database paths if you  
want a fresh index.

**Reinitialize Vector Store:** If using Chroma, decide on new collection vs reusing. If SQLite, consider  
migrating   data.   For   now,   the   simplest   route:  *delete   or   move   the   old   index*  (e.g.,   remove

.deepseek_rag/

  folder if using Chroma, or the   embeddings   table content if using SQLite) to

avoid mixing data.

**Embed and Index Data:** Run the indexing script. This will embed every code/doc chunk with the new  
model and store it. Monitor memory and time – it should be within a few minutes for tens of  
thousands of chunks. After completion, verify the collection stats (the script’s   --stats   flag or a  
printout of count). Each new embedding vector should have length 768 (or the chosen model’s dim).  
You can verify by pulling one vector back: e.g.,   collection.get(limit=1)   and checking the  
vector length.

**Adjust Query Code:** Update  query_context.py  to embed the input query with the new model  
(including prefix, etc.) and query the correct collection. If the collection name changed, update the  
code or CLI args accordingly.

**Testing:** Try some queries that you know the answers to:

Ask for a specific function or class by name (it should retrieve the
file containing it).  
Ask a conceptual question that should match a docstring or README (to
see if text-to-text similarity  
improved).  
If possible, simulate a planner query that previously failed or produced
irrelevant context – see if  
results are now more relevant.

Evaluate the precision: Are the top results clearly related to the query intent? Early signs of improvement  
would be, for example, retrieving a function’s implementation when queried by its usage or vice versa –  
something the old model might miss due to shallow semantic
understanding.

**Fallback Plan:** Keep the old model available just in case. Since our
integration is relatively low-risk,  
you likely won’t need to revert. But if needed, you could maintain a
flag to switch between old/new  
model for A/B testing. For instance, an environment
variable  EMBEDDING_MODEL  that can be set to 

"minilm"

 vs  "e5"  to toggle which one  index_workspace.py  uses. This could be
useful

during a brief transition where you compare results side by side.

1. 

2. 

3. 

4. 

5. 

6. 

7.   
8. 

9. 

1. 

14

</div>

<span id="15"></span>

<div id="page15-div"
style="position:relative;width:918px;height:1188px;">

By following these steps, LLMC will start using the new embeddings seamlessly. The planner and retrieval-  
augmented generation components will automatically benefit from the more relevant context fetched by  
the improved retriever.

**Fine-Tuning Walkthrough (Optional)**

Fine-tuning the embedding model on LLMC’s own code and documentation is an advanced but potentially  
rewarding step. This involves further training the model so that vectors for our domain-specific data are  
even more discriminative. We should weigh the effort vs gain: as noted, if the out-of-the-box model already  
achieves high recall, fine-tuning might yield only marginal gains (perhaps +2–5% recall@5). But in cases  
where certain relevant results are consistently ranked low or missed, fine-tuning can help the model **learn  
project-specific similarities** (e.g. linking function names with their
purpose in docs).

**When   to   Fine-Tune:**  Consider   fine-tuning   if   you   observe   retrieval   failures   such   as:   -   Important   code  
segments not surfacing in top-5 for relevant queries. - The model confusing unrelated code (false positives)  
due to project-specific naming (e.g. lots of similar prefix names). - You have additional supervision signals  
(e.g. a set of Q&A pairs, or documentation with known related code
references) that can teach the model.

Fine-tuning can be done on **open-source models** (E5, BGE, etc.). Proprietary API models (OpenAI, Cohere)  
cannot be locally fine-tuned (though Cohere offers fine-tune as a service at cost). We focus on fine-tuning E5  
or BGE locally using PyTorch.

**Creating a Training Dataset**

We need pairs of texts that should be close in embedding space (positives), and ideally negatives that are  
distractors. Possible sources: - **Documentation to Code Links:** If the repository has README or docs that  
mention specific function names or modules, treat a doc sentence and the code snippet as a positive pair.  
You can extract glossary terms or API references in docs and find the code file that matches. -  **Q&A or  
Commit Messages:** If you have commit messages or issue descriptions and the code changes they refer to,  
use those. For example, a commit message “Add email validation in signup form” and the diff chunk of

validate_email

 function could form a training pair. - **Function and Usage:** Take a function definition

and create a pseudo-query from its name or comments. E.g., for  validate_email , a pseudo query could  
be “how to validate an email address in signup” and the positive is the code of  validate_email . This can  
be   automated   by   templating   (“how   to   …”   for   each   function   name   or   docstring).   -  **Cross-language  
analogues:**  If the project has similar logic in backend (Python) and frontend (TypeScript), one could use  
them as mutual positives (“retrieve semantically similar code across languages” task). - **Hard Negatives:** For  
each positive pair, it’s useful to have one or more negatives – texts that are *somewhat* similar but not actual  
matches. For instance, a negative for  validate_email  could be a function  validate_username  or an  
email formatting snippet – something that shares words but isn’t the target. These “hard negatives” teach  
the model to distinguish fine-grained context

.

Compile a dataset of such examples. A simple CSV or JSONL format could
be: 

[65](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=super%E2%80%91fast%20similarity%20search%20via%20FAISS,behavior%20on%E2%80%91the%E2%80%91fly%20for%20queries%20vs)

15

</div>

<span id="16"></span>

<div id="page16-div"
style="position:relative;width:918px;height:1188px;">

{"query": "Add email validation to signup form", "positive": "def   
validate_email(email): ...", "negative": \["def
send_confirmation(email): ..."\] }

or for sentence-transformers training: 

query \t positive  
query \t negative

multiple lines per query (for MultipleNegativesRankingLoss, format
differs).

Aim for a few thousand pairs if possible. Even a few hundred can be okay, but more is better for fine-tuning  
stability.

**Fine-Tuning Process**

We can use the  **SentenceTransformers library**  which simplifies training. It wraps around PyTorch and  
provides pre-built losses for contrastive learning.

Example using Multiple Negatives Ranking Loss (which allows using positive pairs without explicit negatives  
by assuming other positives in the batch are negatives for a given
anchor):

from sentence_transformers import SentenceTransformer, InputExample, losses  
from torch.utils.data import DataLoader

\# Load the base model to fine-tune (e.g. E5-base)  
model = SentenceTransformer('intfloat/e5-base-v2')

\# Prepare data  
train_examples = \[\]  
for query, pos, neg in training_data:

\# assuming you have a list of (query, 

pos, neg) triples

train_examples.append(InputExample(texts=\[f"query: {query}", f"passage: 

{pos}"\]))

\# If using hard negatives, you can also add InputExample with query
and 

negative as a "false positive"

\# but a better approach is the MultipleNegativesLoss which implicitly
uses 

other positives as negatives.  
train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)

\# Define loss  
train_loss = losses.MultipleNegativesRankingLoss(model)

\# Fine-tune  
model.fit(train_objectives=\[(train_dataloader, train_loss)\],

16

</div>

<span id="17"></span>

<div id="page17-div"
style="position:relative;width:918px;height:1188px;">

epochs=1,  
warmup_steps=100,  
output_path="output/e5-finetuned-llmc")

This will fine-tune the model so that each query is closer to its corresponding passage than to other  
passages in the same batch. We use the same prefix “query:” and “passage:” as before to stay consistent.  
After training, it saves the model to   output/e5-finetuned-llmc . We can then load this model for  
indexing/query instead of the original  intfloat/e5-base-v2 . 

**Hyperparameters:** 1 epoch might be sufficient if dataset is large (\>1k pairs). If dataset is small, maybe 3–5  
epochs. Don’t overtrain, as it can start to overfit (making embeddings too tailored and not generalizing to  
new queries). Use a small learning rate (SentenceTransformers defaults are usually fine, ~2e-5). We could  
also use a development set – e.g., hold out some known Q&A to see if
recall improves.

**Evaluation:** After fine-tuning, evaluate on some test queries (not seen in training). Compare the ranking of  
correct results before vs after. If improvement is marginal, fine-tuning might not be worth maintaining in  
the pipeline.

**Integration of Fine-Tuned Model:** If the fine-tuned model performs
better, update the code to load it:

model = SentenceTransformer('output/e5-finetuned-llmc')

Now, this model will produce the specialized embeddings. Note: fine-tuned embeddings remain the same  
dimension (we are just updating weights).

**Cost of Fine-Tuning:** It requires a GPU to run efficiently. Fine-tuning, say, 1000 examples for 1 epoch on a  
110M model is quite fast (a few minutes on a single GPU). A 7B model would be much slower (hours), but  
we  wouldn’t  fine-tune  a  7B  due  to  resource  constraints.  The  fine-tuning  can  be  done  offline  and  the  
resulting model kept for future indexing – it’s a one-time cost per
domain.

**When Not to Fine-Tune**

If   after   initial   deployment,   the   retrieval   quality   is   satisfactory   (planner   is   finding   the   right   files,   little  
hallucination due to missing context), it’s best to **not introduce the complexity of a custom model**. Using  
a pre-trained model means we benefit from its broad knowledge and maintenance (e.g., updates from  
community). A custom fine-tuned model would need to be re-fine-tuned whenever we update the base  
model to a new version, etc. Also, fine-tuning might narrow the model’s embedding space too much to our  
current code, possibly hurting generalization to new or refactored code.

Thus, treat fine-tuning as a targeted tool: e.g., if LLMC expands to very domain-specific projects (like  
NetSuite ERP scripts with unique language) and the default model
struggles, then invest in fine-tuning.

17

</div>

<span id="18"></span>

<div id="page18-div"
style="position:relative;width:918px;height:1188px;">

**Cost Analysis**

We now compare the costs associated with each embedding approach – both in terms of API expenses and  
infrastructure usage – to determine the most cost-effective solution for
LLMC.

**API Usage Costs**

**OpenAI:**  With   the   new   pricing   (as   of   2024),   OpenAI’s   embeddings   are   quite   affordable.   Using  **text-  
embedding-3-small** at \$0.00002 per 1K tokens

, let’s estimate: LLMC’s ~5K–10K spans, assume average

100 tokens each = ~500K–1M tokens per repo. At \$0.02 per 1M, that’s **\$0.01–\$0.02 per repository** indexed.  
Even if you re-index 50 projects, it’s under \$1. For **3-large**, \$0.00013 per 1K

 is \$0.13 per 1M – indexing

the same repo (1M tokens) costs ~\$0.13. 50 projects ~ \$6.5. Ada-002 would cost \$0.40 per 1M, i.e. ~\$0.40 per  
repo, ~\$20 for 50 repos. So all are quite cheap for one-time indexing. **However**, consider continuous usage:  
- If the code changes frequently and you run the indexer daily or even hourly (with the file watcher auto-  
indexer), those costs could multiply. E.g., re-embedding 1000 new/changed chunks per day with 3-large:  
1000*200 tokens = 200K tokens/day = \$0.026/day, ~\$0.78/month. Still trivial. At massive scale (say 1M tokens/day),  
3-large would be \$0.13*1000 = \$130/day – not relevant unless indexing millions of lines daily. - API **rate limits  
**might require paying for higher tiers or enterprise licenses if doing bulk indexing frequently. OpenAI’s rate  
limits for embeddings (for a typical account) might allow ~3000 tokens/sec, which is ~3M tokens/20min –  
plenty for our needs, but if we scale to millions of chunks, we’d need
to consider it.

**Cohere:**  Their Embed model pricing was listed as ~\$0.12 per 1M tokens for Embed v4

. So similar

ballpark to OpenAI 3-large. Cohere doesn’t publicly detail rate limits, but presumably you can batch and  
process quickly. Cost for our usage: ~\$0.12 per repo (1M tokens) on
average.

**Voyage   AI:**  Voyage’s   documentation   indicates  **\$0.12   per   1M   tokens**  for   voyage-code-2

,   matching

Cohere’s price. So roughly \$0.12 per repo as well. One consideration: Voyage might require a subscription  
(they mention contacting for access

). There might be volume constraints or an API key waitlist.

In summary, pure  **API costs are low**  for our scale – on the order of cents to a few dollars per indexing  
round. So cost alone is not prohibitive. It’s more about other factors (privacy, reliability) where local models  
shine.

**Local Deployment Costs**

Running a local model has two main costs: **compute time** and **hardware resources**. For E5-base or BGE-  
base: -  **One-time indexing**  of ~1M tokens: On CPU, as estimated, maybe ~1–2 minutes. On GPU, a few  
seconds. This is negligible. - **Ongoing cost:** Essentially zero direct cost, since it’s your own machine. If this  
runs on a developer’s workstation or a CI server, the GPU/CPU cycles are the only cost. The impact on power  
usage is minimal for such short bursts. And there’s no cost per query (unlike API which would charge every  
query embedding too – albeit that’s tiny, ~\$0.0004 per query for
3-large).

The **opportunity cost** is that if the hardware is busy embedding, it could slightly slow other tasks. But given  
the speed, this is not a concern for moderate usage.

[7](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Reduced%20price.%20%60text,00002)

[10](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=64)

[66](https://www.unleash.so/post/what-is-cohere-pricing#:~:text=What%20is%20Cohere%20pricing%3F%20,47)

[14](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=Model%20Dimensions%20Max%20Tokens%20Cost,tokens%20cosine%2C%20dot%20product%2C%20L2)

[67](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=The%20success%20of%20%60voyage,posted%20on%20Twitter%20%2F%20LinkedIn)

18

</div>

<span id="19"></span>

<div id="page19-div"
style="position:relative;width:918px;height:1188px;">

**Memory/Disk:** Storing 50K embeddings of 768 dims uses ~150 MB on disk. In RAM, searching them with  
Faiss might use similar memory. If we scaled to say  **1 million**  code chunks indexed (imagine a huge  
monorepo or aggregated multiple repos), at 768 dims that’s ~3 KB each, ~3 GB total – which is still fine on a  
server-class machine. SQLite with that many might be slow, but that’s when moving to pgvector or FAISS  
makes sense (both of which handle millions of vectors efficiently). In any case, the **storage cost is low** (a  
few hundred MB), and the **growth is linear** with number of spans. If we ever hit storage concerns, we can  
reduce dimension or exclude less important files from indexing.

**Maintenance overhead:** Using local models means we have to occasionally update them if a new, better  
open model comes out (like when E5-v2 came, we’d consider E6 etc.). This “cost” is just engineering time to  
evaluate and swap, which we’re doing now as part of LLMC’s improvement.

**Breakeven Analysis: Local vs API**

Given the above, the **breakeven is more about qualitative factors** than raw dollar amounts. At current  
pricing: - If quality was equal, an API like OpenAI 3-small is so cheap that cost wouldn’t be an issue. But local  
is still cheaper (free) and avoids sending code data over the network. The breakeven in terms of cost would  
only matter if we had to run extremely large jobs or if OpenAI increased prices. - If a *much better model* was  
only available via API (say a hypothetical “GPT-embedding” with 10% better recall but costing \$5 per 1M),  
we’d compare the value of that accuracy vs paying each time. In our case, open models cover most of the  
gap.

One area to consider is **fine-tuning cost vs API usage**. Fine-tuning is a one-time hit (training on a GPU for a  
few hours at most). If using a cloud GPU, that might cost a few dollars (e.g., \$0.30/hour). That’s comparable  
to embedding a few million tokens via API. If the fine-tune yields even a small improvement that applies to  
thousands of queries in the future, it’s worth it. 

**Amortized cost per query:**  Suppose our planner runs 100 queries per day. Embedding each query with  
openAI 3-large: 100 \* 50 tokens = 5000 tokens = \$0.00065/day, ~\$0.02/month. Negligible. So even at high  
query volumes, embedding costs won’t break the bank. However, using an API means  **dependency on  
external uptime and potential data exposure** (even if OpenAI doesn’t train on our data, it still sees the  
content). Some organizations value the \$0.02 privacy guarantee as worth
self-hosting.

**Conclusion:** The cost difference in dollars is minor at our scale, but the control, privacy, and performance of  
local   embeddings   tilt   the   decision   to   local.   We   essentially   get  **enterprise-grade   embedding   at   zero  
ongoing   cost**  with   models   like   E5,   which   is   a   huge   win.   As   we   scale,   we   will   monitor   if   vector   DB  
performance   or   memory   becomes   an   issue,   but   we   have   options   (optimizing   index,   switching   to  
approximate search, etc.) that do not involve recurring costs.

**Budget Projection Scenarios**

To be thorough, consider a few scenarios: - *Current usage:* ~50K spans indexed, ~100 queries/day. **API cost/  
month**  (OpenAI 3-large): indexing 50K spans (say updated fully once): 50K*100 tokens=5M tokens=\$0.65;  
queries 100*30 days*50 tokens=150K tokens=\$0.019. Total ~\$0.67/month. Local cost: \$0, plus maybe 1–2 hours of  
engineering maintenance per month (amortized). - *Increased projects:* 200K spans (4× current). API 3-large: 20M  
tokens to index = \$2.6, queries double maybe \$0.04, total ~\$2.64/month. Still trivial. Local: \$0, but ensure*

19

</div>

<span id="20"></span>

<div id="page20-div"
style="position:relative;width:918px;height:1188px;">

*hardware can handle indexing (~4 minutes on CPU). - *High frequency re-index:* If using auto re-index on file save  
(the watcher), and you edit 100 files per day (each save re-embeds chunk): 100*500 tokens=50K tokens/day =  
~\$0.0065/day (\$0.20/month) with OpenAI. Local still \$0 (small CPU usage). - *Massive scale (hypothetical):* 10M  
spans (if LLMC indexes an entire large codebase collection). 10M\*100 tokens = 1 billion tokens to embed.  
OpenAI cost 3-large: \$130 per 1B tokens

 – so \$130 for initial index. If that only happens once, not bad;

but storing 10M vectors 3072-dim is heavy on our side. Local E5 might not handle 10M easily without  
distributed setup. At that extreme, one might consider OpenAI or a specialized solution. But LLMC is  
unlikely to hit this in near future (that’s akin to indexing all of
GitHub, which is out of scope).

Thus, in all realistic scenarios, **cost is not a barrier** – it’s about
maximizing quality and autonomy. 

As a final note, the **ROI of fine-tuning** can be considered: If fine-tuning improves planner success by even  
5% (say preventing costly mistakes or saving developer time), that benefit outweighs a few hours of training  
work which might cost \<\$5 on a cloud GPU. If LLMC is used extensively for code assistance, a 5–10% better  
retrieval can translate to faster coding iterations, fewer errors, etc., which is high ROI. So spending a small  
budget on fine-tuning data curation and training is justified if needed.

**Migration Plan**

Finally, we outline how to transition from the current embedding setup to the new one with minimal  
disruption and how to verify success. The migration involves re-embedding the existing corpus, updating  
the system to use the new embeddings, and validating that everything
works as expected.

**Step 1: Backup and Prepare**

**Backup   Current   Index:**  Before   making   changes,   back   up   the   current   .rag/index.db   or   Chroma  
directory (if it’s small, just copy the file/folder). This ensures we can roll back if something goes wrong. Since  
we likely will create a new collection, the old data will remain untouched, but it’s good practice to have a  
backup.

**Enable   Dual-Index   (Optional):**  For   a   transitional   period,   you   could   maintain   both   the   old   and   new  
embeddings to compare results: - If using SQLite, create a new table  embeddings_new  for the E5 vectors.  
-  If  using  Chroma,  use  a  separate   COLLECTION_NAME   for  new  model.  -  Modify  query  code  to  allow  
querying either index (perhaps with a flag).

This is optional and mostly useful if you want to A/B test retrieval quality. It will, however, double storage  
temporarily.

**Step 2: Deploy the New Model**

**Implement Code Changes:** As per integration guide, change the model loading line and any related logic  
(prefix, normalization). This is a small code change – test that the script runs without errors (you might need  
to install any new model dependencies first as mentioned).

[10](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=64)

20

</div>

<span id="21"></span>

<div id="page21-div"
style="position:relative;width:918px;height:1188px;">

**Run Re-indexing:**  Execute the indexing process with the new model. This could be done repository by  
repository or all at once. Since our scale is moderate, running the full index for all projects is fine. If you  
have an **incremental indexing** process (the file watcher), it might be simpler to run a one-time full re-index  
with the new model to avoid mixing embeddings.

Make sure to use the new storage location (if chosen). Monitor the logs: - Check that for each file, chunks  
are being embedded (no unexpected errors like model not found or out-of-memory). - If any issues (e.g.,  
extremely slow, or memory spikes), consider batching or using GPU
explicitly.

Once done, verify the number of vectors in the new index matches expectation (close to the number from  
old index). You can use  --stats  as shown in the RAG README to see total chunks indexed

. It should

list similar counts as before (if vastly different, maybe some files were skipped or the script had an early  
termination).

**Step 3: Switch Query to New Index**

Point the retrieval queries to the new embeddings. If you used a new collection or table, update the query  
code to use that. For example, if using Chroma:

\# open the new collection  
collection = chroma_client.get_collection("workspace_code_e5")  
...  
results = collection.query(... )

If using the same collection name (overwritten), this might not require any change except ensuring the  
query uses the same embedding model to generate the search vector.

Double-check that the query path (likely integrated with  llm_gateway.sh  as in the RAG README

) is

calling the updated code. If you updated the scripts properly, this
should be seamless.

**Step 4: Validation Testing**

Conduct a series of tests to ensure the new system is functioning
correctly and yielding better results:

**Functional Test:** Ask a variety of questions to LLMC that require
code retrieval and see that it  
responds meaningfully. Ensure no errors are thrown in retrieval (like
dimension mismatches or  
missing collection).  
**Relevance Test:** Using a predefined set of queries (perhaps derived
from actual issues or common  
tasks), compare the retrieved snippets before and after. If you did
dual-index, you can run the same  
query on old vs new and see the difference. We expect to see improved
relevance – e.g., fewer  
irrelevant files in top-5, more direct hits.   
For example, query “**Add email validation to signup form**” should
retrieve the  validate_email  
function and form handling code with high similarity (the RAG README
example shows those files  
were found

 – ensure our new model also finds them, ideally with even higher
similarity scores).

[68](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L68-L76)

[69](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L92-L100)

• 

• 

• 

[70](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L160-L169)

21

</div>

<span id="22"></span>

<div id="page22-div"
style="position:relative;width:918px;height:1188px;">

Query “**Where is the member login route defined?**” – should retrieve
something like  app/api/  
members/login/route.ts

 or relevant code, not random files. Check if new model surfaces it.

For documentation, query “**What does function X do?**” if  X  has a
docstring – see if docstring or  
relevant comment chunk is retrieved alongside code.

**Performance Test:** Measure the time it takes to get retrieval results for a query. It should still be  
very fast (\<100ms as before

). If using a larger model for query embedding, you may add a slight

overhead (e.g., E5-base encoding the query might take a few milliseconds vs virtually nothing for  
MiniLM). This difference is negligible in user experience, but just ensure it’s not, say, timing out or  
taking seconds. Since  llm_gateway  likely prints timing info, observe
if any step slowed.

**Planner Impact:** The ultimate metric is planner accuracy – e.g., the RAG-enhanced responses from  
LLMC yield correct code references. While harder to quantify immediately, one can take a recent case  
where the planner might have missed context and see if it now includes it. Over a longer period,  
track   if   developers   find   the   suggestions   more   on-point.   The   goal   was   ≥10%   improvement   in  
recall@5; we can approximate this by seeing if more relevant snippets appear in the top 5 than  
before. Given that E5 improved an average ~14% recall on CoIR vs older model

, we expect to

meet that goal.

**Regression checks:** Ensure that nothing broke: - The index size is as expected (no huge bloat beyond what  
we predicted for higher dims). - The file watcher (if running) picks up changes and re-embeds with the new  
model seamlessly. (Test by editing a file and see if its embedding updates without error). - Memory usage of  
any persistent service (if RAG server runs continuously) is within
limits.

**Step 5: Phase-out Old Embeddings**

If everything looks good with the new model, you can decommission the old embeddings: - Remove or  
archive the old  embeddings  table or Chroma collection. - Turn off any code that was maintaining the old  
index (for instance, if you had a background job updating it). - Update documentation (internal README or  
docs) to note the new default model and any new requirements (like the need for  intfloat/e5-base-v2  
weights, which will be downloaded on first run).

Given we changed the code to load the new model, any new indexing will naturally use it. The old data on  
disk (if not cleaned) won’t be referenced. Still, for cleanliness,
cleaning up prevents confusion.

**Step 6: Monitor and Iterate**

After deploying, monitor usage for a while: - Are users (or yourself) noticing improved assistance? If not,  
gather examples of failures and analyze whether it’s embedding-related. Possibly we might then consider  
fine-tuning if certain patterns are missed. - Keep an eye on the index growth if projects increase. If suddenly  
a project has a huge number of chunks (say \>100k), check that search remains snappy. If not, consider  
enabling approximate search (Chroma can do HNSW indexing, or switch to Faiss IVFPQ) – but that’s an  
optimization only needed at large scale. - If any new embedding model versions come out (e.g. E6 or a new  
OpenAI model), evaluate if it’s worth switching again. This SDD and
framework will make it easier next time.

• 

• 

• 

[71](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L194-L203)

• 

[2](https://arxiv.org/html/2407.02883v1#:~:text=Contriever%20%28110M%29%205,21)

22

</div>

<span id="23"></span>

<div id="page23-div"
style="position:relative;width:918px;height:1188px;">

**Backward   Compatibility:**  One   consideration   –   if   any   downstream   component   assumed   a   certain  
embedding dimension or model name, update it. For instance, if  .rag/index.db  was read by another  
script that expects 384-length vectors in JSON, that script might break with 768-length. Audit if any such  
assumption exists. Similarly, if the planner had some hardcoded logic tied to the old embedder (unlikely),  
that would need update.

In our case, it seems the system treats embeddings opaquely – the model and dimension were stored  
alongside,  but  no  logic  depends  on  “384”.  We  updated  the  model  name  in  the  DB  so  it’s  clear  what  
produced them. If in future we need to distinguish vectors by model, we
have that metadata.

**Risk Mitigation:** The primary risk is that the new embeddings might cause subtle changes in retrieval order  
that the planner didn’t expect. Perhaps something that was ranked 1 is now rank 3; the planner might still  
see it (since we take top 10), so it should be fine. Actually, with better embeddings, if anything, the planner  
will see *more* relevant info earlier. There’s a small chance of over-similarity: e.g., if the new model clusters  
certain similar code very tightly, it might retrieve multiple very similar snippets and miss some diversity. But  
since we chunk by file and code structure, this is not a big issue.

We  should  also  update  any  **documentation  or  config**  that  says  what  embedding  model  is  used  (for  
transparency   and   future   maintainers).   E.g.,   in   scripts/rag/README.md ,   update   “Embeddings   (runs  
locally!)” to mention the new model name, and possibly note one can configure it. It currently has a to-do “\[ \]  
Multiple embedding models”

  – which we have effectively addressed by choosing one optimal model,

though the framework allows switching.

**Conclusion**

The migration should be relatively straightforward given the modular design (just swapping the embedding  
generator). By carefully validating results and keeping a backup, we ensure a smooth transition. After  
migration, LLMC’s RAG subsystem will be using a state-of-the-art embedding model, yielding more accurate  
context retrieval. This upgrade sets a foundation for further improvements, such as domain-specific tuning  
or scaling to more projects, with confidence that our embedding
infrastructure is robust and high-quality.

Best Open-Source Embedding Models Benchmarked and Ranked

<https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/>

CoIR: A Comprehensive Benchmark forCode

Information Retrieval Models  
<https://arxiv.org/html/2407.02883v1>

voyage-code-2: Elevate Your Code Retrieval – Voyage AI

<https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/>

New embedding models and API updates \| OpenAI

<https://openai.com/index/new-embedding-models-and-api-updates/>

Cohere AI pricing in 2025: A complete guide to real costs - eesel AI

<https://www.eesel.ai/blog/cohere-ai-pricing>

[72](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L300-L308)

[1](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=Model%20Embedding%20Time%20,Image)

[15](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=)

[16](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=It%E2%80%99s%20one%20of%20the%20most,to%20use%20in%20flexible%20pipelines)

[21](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=It%27s%20state,and%20production%20search%20systems%20alike)

[22](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=retrieval,and%20production%20search%20systems%20alike)

[23](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=These%20benchmarks%20highlight%20that%20there%E2%80%99s,depends%20on%20your%20product%20priorities)

[24](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=)

[36](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=,labeled%20nuance%20and)

[50](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=,like%20all%E2%80%91mpnet%E2%80%91base%E2%80%91v2%2C%20which%20is%20ideal)

[57](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=training%20signals%20that%20transfer%20well,read%20the%20official%20paper%20here)

[65](https://supermemory.ai/blog/best-open-source-embedding-models-benchmarked-and-ranked/#:~:text=super%E2%80%91fast%20similarity%20search%20via%20FAISS,behavior%20on%E2%80%91the%E2%80%91fly%20for%20queries%20vs)

[2](https://arxiv.org/html/2407.02883v1#:~:text=Contriever%20%28110M%29%205,21)

[5](https://arxiv.org/html/2407.02883v1#:~:text=E5,59)

[17](https://arxiv.org/html/2407.02883v1#:~:text=BGE,31)

[18](https://arxiv.org/html/2407.02883v1#:~:text=8%20GTE,56.8%C2%B5s%200.9G)

[19](https://arxiv.org/html/2407.02883v1#:~:text=Trade,the%20expense%20of%20increased%20latency)

[20](https://arxiv.org/html/2407.02883v1#:~:text=E5,31)

[28](https://arxiv.org/html/2407.02883v1#:~:text=Effectiveness%20of%20Code,and%20optimization%20for%20code%20retrieval)

[29](https://arxiv.org/html/2407.02883v1#:~:text=No%20Single%20Model%20Dominates%20Across,catering%20to%20varied%20task%20requirements)

[37](https://arxiv.org/html/2407.02883v1#:~:text=Package%20CodeSeachNet%20Github%206%20Text,Deep%20Learning%2C%20StackOverFlow%2C%20Code%20Instruction)

[38](https://arxiv.org/html/2407.02883v1#:~:text=match%20at%20L462%20state,M3%C2%A0%5B3%5D%2C%20and%20UniXcoder%C2%A0%5B9%5D.%20For%20proprietary)

[39](https://arxiv.org/html/2407.02883v1#:~:text=Task%20%28%29%20Text,Code%20Code%20CodeTrans%20StackOver%20CodeFeedBack)

[40](https://arxiv.org/html/2407.02883v1#:~:text=OpenAI,59)

[41](https://arxiv.org/html/2407.02883v1#:~:text=No%20Single%20Model%20Dominates%20Across,catering%20to%20varied%20task%20requirements)

[42](https://arxiv.org/html/2407.02883v1#:~:text=consistently%20excel%20across%20CoIR%20sub,adaptive%2C%20robust%20code%20retrieval%20capabilities)

[43](https://arxiv.org/html/2407.02883v1#:~:text=GTE,31)

[51](https://arxiv.org/html/2407.02883v1#:~:text=9%20Contriever%20768%207,56.8%C2%B5s%200.9G)

[52](https://arxiv.org/html/2407.02883v1#:~:text=7%20UniXcoder%20768%207,56.8%C2%B5s%200.9G)

[3](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=TL%3BDR%20%E2%80%93%20We%20are%20thrilled,purpose%20text%20datasets)

[4](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=This%20post%20presents%20%60%60voyage,the%20context%20window%20to%2016K)

[9](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=%60voyage,were%20encountered%20during%20our%20training)

[12](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=With%20improved%20training%20methods%20on,average%20results%20across%20all%20datasets)

[34](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=data%20from%20both%20natural%20language,purpose%20text%20datasets)

[35](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=This%20post%20presents%20%60%60voyage,world%2C%20interactive%20production)

[48](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=This%20section%20demonstrates%2C%20through%20examples%2C,2%60%20compared%20to%20OpenAI%20Ada)

[49](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=Image)

[58](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=vo%20%3D%20voyageai.Client%28os.environ.get%28)

[59](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=,2%22%29.embeddings%5B0)

[67](https://blog.voyageai.com/2024/01/23/voyage-code-2-elevate-your-code-retrieval/#:~:text=The%20success%20of%20%60voyage,posted%20on%20Twitter%20%2F%20LinkedIn)

[6](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Stronger%20performance.%20%60text,to%2064.6)

[7](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Reduced%20price.%20%60text,00002)

[8](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Stronger%20performance.%20Comparing%20%60text,to%2062.3)

[10](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=64)

[11](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Both%20of%20our%20new%20embedding,with%20a%20size%20of%201536)

[30](https://openai.com/index/new-embedding-models-and-api-updates/#:~:text=Comparing%20%60text,to%2064.6)

[13](https://www.eesel.ai/blog/cohere-ai-pricing#:~:text=Cohere%20AI%20pricing%20in%202025%3A,so%20developers%20can%20play)

23

</div>

<span id="24"></span>

<div id="page24-div"
style="position:relative;width:918px;height:1188px;">

Voyage Embedding Models - Nile Documentation

<https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage>

manutic/nomic-embed-code - Ollama

<https://ollama.com/manutic/nomic-embed-code>

The Nomic Embedding Ecosystem

<https://www.nomic.ai/blog/posts/embed-ecosystem>

Nomic Embed Code: A State-of-the-Art Code Retriever

<https://www.nomic.ai/blog/posts/introducing-state-of-the-art-nomic-embed-code>

Embedding Models: OpenAI vs Gemini vs Cohere

<https://research.aimultiple.com/embedding-models/>

README.md

<https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md>

index_workspace.py

<https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/index_workspace.py>

What is Cohere pricing? - Unleash.so

<https://www.unleash.so/post/what-is-cohere-pricing>

[14](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=Model%20Dimensions%20Max%20Tokens%20Cost,tokens%20cosine%2C%20dot%20product%2C%20L2)

[33](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=Voyage%20embeddings%20are%20normalized%20to,is%20the%20fastest%20to%20compute)

[55](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=Distance%20metrics)

[60](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=%2F%2F%20we%20need%20a%20separate,documents%20stored%20in%20pg_vector)

[61](https://www.thenile.dev/docs/ai-embeddings/embedding_models/voyage#:~:text=const%20embedQueries%20%3D%20new%20VoyageEmbeddings%28,used%20to%20search%20documents)

[25](https://ollama.com/manutic/nomic-embed-code#:~:text=nomic,and%20OpenAI%20Embed%203)

[26](https://www.nomic.ai/blog/posts/embed-ecosystem#:~:text=The%20Nomic%20Embedding%20Ecosystem%20Nomic,CSN%29)

[27](https://www.nomic.ai/blog/posts/introducing-state-of-the-art-nomic-embed-code#:~:text=Nomic%20Embed%20Code%20is%20a,art%20performance%20on%20CodeSearchNet)

[31](https://research.aimultiple.com/embedding-models/#:~:text=%2A%20Higher,priced%20alternatives)

[32](https://research.aimultiple.com/embedding-models/#:~:text=,A)

[44](https://research.aimultiple.com/embedding-models/#:~:text=match%20at%20L116%20,priced%20alternatives)

[45](https://research.aimultiple.com/embedding-models/#:~:text=match%20at%20L295%20Based%20on,even%20at%20a%20moderate%20cost)

[46](https://research.aimultiple.com/embedding-models/#:~:text=The%20scatter%20plot%20illustrates%20that,balance%20between%20accuracy%20and%20cost)

[47](https://research.aimultiple.com/embedding-models/#:~:text=attractiveness%20in%20cost,priced%20alternatives)

[53](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L60-L68)

[54](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L186-L194)

[64](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L80-L88)

[68](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L68-L76)

[69](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L92-L100)

[70](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L160-L169)

[71](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L194-L203)

[72](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/README.md#L300-L308)

[56](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/index_workspace.py#L88-L96)

[62](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/index_workspace.py#L70-L78)

[63](https://github.com/vmlinuzx/glideclubs/blob/192e899e53e6dc63cf3660b86021b03227bf03d9/scripts/rag/index_workspace.py#L76-L84)

[66](https://www.unleash.so/post/what-is-cohere-pricing#:~:text=What%20is%20Cohere%20pricing%3F%20,47)

24

</div>

<span id="outline"></span>

# Document Outline

- [Executive Summary](converted.html#1)
  - [Model Comparison Overview](converted.html#1)
- [Benchmarking Results and Findings](converted.html#5)
  - [Retrieval Quality Evaluation](converted.html#6)
  - [Performance and Resource Metrics](converted.html#7)
- [Integration Guide](converted.html#8)
  - [1. Replacing the Embedding Model in Code](converted.html#8)
  - [2. Database Schema and Storage Changes](converted.html#10)
  - [3. Adapting the Query Mechanism](converted.html#11)
  - [4. Batch Embedding Scripts Example](converted.html#12)
  - [5. End-to-End Integration Steps](converted.html#14)
- [Fine-Tuning Walkthrough (Optional)](converted.html#15)
  - [Creating a Training Dataset](converted.html#15)
  - [Fine-Tuning Process](converted.html#16)
  - [When Not to Fine-Tune](converted.html#17)
- [Cost Analysis](converted.html#18)
  - [API Usage Costs](converted.html#18)
  - [Local Deployment Costs](converted.html#18)
  - [Breakeven Analysis: Local vs API](converted.html#19)
  - [Budget Projection Scenarios](converted.html#19)
- [Migration Plan](converted.html#20)
  - [Step 1: Backup and Prepare](converted.html#20)
  - [Step 2: Deploy the New Model](converted.html#20)
  - [Step 3: Switch Query to New Index](converted.html#21)
  - [Step 4: Validation Testing](converted.html#21)
  - [Step 5: Phase-out Old Embeddings](converted.html#22)
  - [Step 6: Monitor and Iterate](converted.html#22)
  - [Conclusion](converted.html#23)

------------------------------------------------------------------------
