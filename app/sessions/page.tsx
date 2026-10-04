import Workspace from '@/components/workspace';
import {requireChatGPTUser} from '@/app/chatgpt-auth';
import {owner} from '@/lib/workspace';
export const dynamic='force-dynamic';
export default async function Page(){await requireChatGPTUser('/sessions');if(!await owner())return <main className="access-error"><h1>Приватна статистика</h1><a href="/">Публічний журнал</a></main>;return <Workspace mode="sessions"/>;}
