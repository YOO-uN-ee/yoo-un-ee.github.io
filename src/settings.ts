export const profile = {
	fullName: 'Jiyoon Pyo',
	title: 'Ph.D. Student',
	institute: 'University of Minnesota-Twin Cities',
	author_name: 'Jiyoon Pyo', // Author name to be highlighted in the papers section
	research_areas: [
		{title: 'Natural Language Processing', description: '', field: 'computer science'},
		{title: 'GeoAI', description: '', field: 'computer science'}
		// { title: 'Physics', description: 'Brief description of the research interest', field: 'physics' },
	],
}

// Set equal to an empty string to hide the icon that you don't want to display
export const social = {
	email: 'jiyoonp0228@gmail.com',
	linkedin: 'https://www.linkedin.com/in/yoo-un-ee/',
	x: 'https://x.com/yoo_un_ee',
	github: 'https://github.com/YOO-uN-ee',
	gitlab: '',
	scholar: '',
	inspire: '',
	arxiv: '',
	orcid: 'https://orcid.org/0009-0000-8746-4411',
}

export const template = {
	website_url: 'https://yoo-un-ee.github.io', // Astro needs to know your site’s deployed URL to generate a sitemap. It must start with http:// or https://
	menu_left: false,
	transitions: true,
	lightTheme: 'fantasy', // Select one of the Daisy UI Themes or create your own
	darkTheme: 'night', // Select one of the Daisy UI Themes or create your own
	excerptLength: 200,
	postPerPage: 5,
    base: '' // Repository name starting with /
}

export const seo = {
	default_title: 'Jiyoon Pyo',
	default_description: 'Welcome to Jiyoon\'s webpage!',
	default_image: '/images/astro-academia.png',
}
