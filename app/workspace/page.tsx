import Workspace from '@/components/workspace';
import {requireChatGPTUser} from '@/app/chatgpt-auth';
import {owner} from '@/lib/workspace';
export const dynamic='force-dynamic';
export default async function Page(){await requireChatGPTUser('/workspace');if(!await owner())return <main className="access-error"><h1>Особистий кабінет</h1><p>Доступ має лише власник сайту.</p><a href="/">Публічний журнал</a></main>;return <Workspace mode="private"/>;}
