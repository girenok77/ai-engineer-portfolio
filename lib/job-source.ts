export type JobSource='nav'|'dou'|'other';
export const jobSources:Record<JobSource,string>={nav:'NAV',dou:'DOU',other:'Інше'};
export function jobSource(value:string):JobSource{
 try{const host=new URL(value).hostname.toLowerCase();return host==='arbeidsplassen.nav.no'?'nav':host==='jobs.dou.ua'?'dou':'other';}catch{return 'other';}
}
