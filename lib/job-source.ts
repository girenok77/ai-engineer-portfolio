export type JobSource='nav'|'dou'|'linkedin'|'other';
export const jobSources:Record<JobSource,string>={nav:'NAV',dou:'DOU',linkedin:'LinkedIn',other:'Інше'};
export function jobSource(value:string):JobSource{
 try{const host=new URL(value).hostname.toLowerCase();return host==='arbeidsplassen.nav.no'?'nav':host==='jobs.dou.ua'?'dou':(host==='linkedin.com'||host.endsWith('.linkedin.com'))?'linkedin':'other';}catch{return 'other';}
}
