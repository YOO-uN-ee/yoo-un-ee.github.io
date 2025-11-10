export const experiences = [
	{
		company: '',
		time: '',
		title: '',
		location: '',
		description: '',
	},
	// {
	// 	company: 'Radium Institute (Institut du Radium)',
	// 	time: '1914 - 1934',
	// 	title: 'Director',
	// 	location: 'Paris, France',
	// 	description: 'Led groundbreaking studies on radioactivity and mentored future Nobel Prize laureates.',
	// },
];

export const education = [
	{
		school: 'University of Minnesota - Twin Cities',
		time: '2023 -  Current',
		degree: 'Ph.D. in Computer Science',
		location: 'Minnesota, US',
		description: '',
	},

	{
		school: 'University of Minnesota - Twin Cities',
		time: '2023 - 2025',
		degree: 'Master\'s in Computer Science',
		location: 'Minnesota, US',
		description: '',
	},

	{
		school: 'The Cooper Union for the Advancement of Science and Art',
		time: '2021 - 2023',
		degree: 'Master\'s in Electrical Engineering',
		location: 'New York, US',
		description: 'Thesis: Detection and Replacement of Neologisms for Translation',
	},

	{
		school: 'The Cooper Union for the Advancement of Science and Art',
		time: '2019 - 2023',
		degree: 'Bachelor\'s in Electrical Engineering',
		location: 'New York, US',
		description: 'Minor: Computer Science',
	},
	// {
	// 	school: 'University of Paris',
	// 	time: '1891 - 1895',
	// 	degree: 'Master’s in Physics and Mathematics',
	// 	location: 'Paris, France',
	// 	description: 'Graduated at the top of her class in physics and second in mathematics.',
	// },
];

export const skills = [
	{
		title: '',
		description: '',
	},
	// {
	// 	title: 'Experimental Techniques',
	// 	description: 'Spectroscopy, Isolation of Radioactive Elements, Radiation Measurement',
	// },
];

export const publications = [
	{
		title: 'FRIEDA: Benchmarking Multi-Step Cartographic Reasoning in Vision-Language Models',
		authors: 'Jiyoon Pyo, Yuankun Jiao, Dongwon Jung, Zekun Li, Leeje Jang, Sofia Kirsanova, Jina Kim, Yijun Lin, Qin Liu, Junyi Xie, Hadi Askari, Nan Xu, Muhao Chen, Yao-Yi Chiang',
		journal: 'Under Review',
		time: '2025',
		// link: '#',
		github: "https://github.com/knowledge-computing/FRIEDA-dataset",
		// slides: "",
		abstract: 'Cartographic reasoning is the skill of interpreting geographic relationships by aligning legends, map scales, compass directions, map texts, and geometries across one or more map images. Although essential as a concrete cognitive capability and for critical tasks such as disaster response and urban planning, it remains largely unevaluated. Building on progress in chart and infographic understanding, recent large vision language model (LVLM) works on map visual question-answering (VQA) often simplify maps as a special case of charts. In contrast, map VQA demands comprehension of layered symbology (e.g., symbols, geometries, and text labels) as well as spatial relations tied to orientation and distance that often span multiple maps and are not captured by chart-style evaluations. To address this gap, we introduce FRIEDA, a benchmark for testing complex open-ended cartographic reasoning in LVLMs. FRIEDA sources real map images from documents and reports in various domains (e.g., geology, urban planning, and environmental assessment) and geographical areas. Following classifications in Geographic Information System (GIS) literature, FRIEDA targets all three categories of spatial relations: topological (border, equal, intersect, within), metric (distance), and directional (orientation). All questions require multi-step inference, and many require cross-map grounding and reasoning. We evaluate eleven state-of-the-art LVLMs under two settings: (1) the direct setting, where we provide the maps relevant to the question, and (2) the contextual setting, where the model may have to identify the maps relevant to the question before reasoning. Even the strongest models, Gemini-2.5-Pro and GPT-5-Think, achieve only 38.20% and 37.20% accuracy, respectively, far below human performance of 84.87%. These results reveal a persistent gap in multi-step cartographic reasoning, positioning FRIEDA as a rigorous benchmark to drive progress on spatial intelligence in LVLMs.',
	},
	{
		title: 'Augmenting Human-Centered Racial Covenant Detection and Georeferencing with Plug-and-Play NLP Pipelines',
		authors: 'Jiyoon Pyo, Yuankun Jiao, Yao-Yi Chiang, Michael Corey',
		journal: 'GeoHCC \'25: Proceedings of the 1st ACM SIGSPATIAL International Workshop on Human-Centered Geospatial Computing',
		time: '2025',
		link: 'https://arxiv.org/abs/2509.05829',
		// github: "",
		slides: "",
		abstract: 'Though no longer legally enforceable, racial covenants in twentieth-century property deeds continue to shape spatial and socioeconomic inequalities. Understanding this legacy requires identifying racially restrictive language and geolocating affected properties. The Mapping Prejudice project addresses this by engaging volunteers on the Zooniverse crowdsourcing platform to transcribe covenants from scanned deeds and link them to modern parcel maps using transcribed legal descriptions. While the project has explored automation, it values crowdsourcing for its social impact and technical advantages. Historically, Mapping Prejudice relied on lexicon-based searching and, more recently, fuzzy matching to flag suspected covenants. However, fuzzy matching has increased false positives, burdening volunteers and raising scalability concerns. Additionally, while many properties can be mapped automatically, others still require time-intensive manual geolocation. We present a human-centered computing approach with two plug-and-play NLP pipelines: (1) a context-aware text labeling model that flags racially restrictive language with high precision and (2) a georeferencing module that extracts geographic descriptions from deeds and resolves them to real-world locations. Evaluated on historical deed documents from six counties in Minnesota and Wisconsin, our system reduces false positives in racial term detection by 25.96% while maintaining 91.73% recall and achieves 85.58% georeferencing accuracy within 1x1 square-mile ranges. These tools enhance document filtering and enrich spatial annotations, accelerating volunteer participation and reducing manual cleanup while strengthening public engagement.',
	},
	{
		title: 'Exploiting LLMs and Semantic Technologies to Build a Knowledge Graph of Historical Mining Data',
		authors: 'Craig A. Knoblock, Binh Vu, Basel Shbita, Yao-Yi Chiang, Pothula Punith Krishna, Xiao Lin, Goran Muric, Jiyoon Pyo, Adriana Trejo-Sheu, Meng Ye',
		journal: 'The Semantic Web – ISWC 2025: 24th International Semantic Web Conference',
		time: '2025',
		link: 'https://dl.acm.org/doi/10.1007/978-3-032-09530-5_26',
		github: "",
		// slides: "",
		abstract: 'Locating new sources of critical minerals begins with understanding where these minerals have been found in the past. However, historical data about mineral occurrences is often locked in disparate, unstructured, and inconsistent formats, ranging from government databases to mining reports and journal articles. To address this challenge, we have developed a set of scalable technologies that extract, normalize, and semantically integrate information from these sources into a unified knowledge graph. Our approach combines ontology-driven modeling, large-language models for information extraction and classification, and tools for linking and validating data across sources. The result is a semantically enriched, queryable knowledge graph that supports reproducible analysis, expert validation, and geoscientific applications such as deposit classification and prospectivity modeling. Through this work, we have successfully integrated information from hundreds of thousands of records across multiple historical sources to build one of the world’s largest repositories of structured data on critical minerals.',
	},
	{
		title: 'Leveraging Large Language Models for Generating Labeled Mineral Site Record Linkage Data ',
		authors: 'Jiyoon Pyo, Yao-Yi Chiang',
		journal: 'GeoAI \'24: Proceedings of the 7th ACM SIGSPATIAL International Workshop on AI for Geographic Knowledge Discovery',
		time: '2024',
		link: 'https://dl.acm.org/doi/10.1145/3687123.3698298',
		github: "https://github.com/DARPA-CRITICALMAAS/umn-ta2-mineral-site-linkage",
		slides: "",
		abstract: 'Record linkage integrates diverse data sources by identifying records that refer to the same entity. The record linkage task is applicable and essential in various domains, such as history and epidemiology. In the context of mineral site records, accurate record linkage is crucial for identifying and mapping mineral deposits. Properly linking records that refer to the same mineral deposit helps define the spatial coverage of mineral areas, benefiting resource identification and site data archiving. Mineral site record linkage falls under the spatial record linkage category since the records contain information about the physical locations and non-spatial attributes in a tabular format. The task is particularly challenging due to the heterogeneity and vast scale of the data. While prior research employs pre-trained discriminative language models (PLMs) on spatial entity linkage, they often require substantial amounts of curated ground-truth data for fine-tuning. Gathering and creating ground truth data is both time-consuming and costly. Therefore, such approaches are not always feasible in real-world scenarios where gold-standard data are unavailable. Although large generative language models (LLMs) have shown promising results in various natural language processing tasks, including record linkage, their high inference time and resource demand present challenges. We propose a method that leverages an LLM to generate training data and fine-tune a PLM to address the training data gap while preserving the efficiency of PLMs. Our approach achieves over 45% improvement in F1 score for record linkage compared to traditional PLM-based methods using ground truth data while reducing the inference time by nearly 18 times compared to relying on LLMs. Additionally, we offer an automated pipeline that eliminates the need for human intervention, highlighting this approach\'s potential to overcome record linkage challenges.',
	},
];

export const teaching = [
	{
		title: 'CSCI4541: Introduction to Natural Language Processing',
		semester: 'Fall 2025',
	},
	{
		title: 'CSCI5523: Introduction to Data Mining',
		semester: 'Spring 2024',
	},
	{
		title: 'CSCI1913: Introduction to Algorithms, Data Structures, and Program Development',
		semester: 'Fall 2023',
	},
];
