import {publicState,response} from '@/lib/workspace';
export async function GET(){try{return response(await publicState());}catch{return response({error:'Не вдалося завантажити журнал. Спробуй ще раз.'},503);}}
