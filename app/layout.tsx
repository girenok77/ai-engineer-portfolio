import type {Metadata} from 'next';
import './globals.css';
export const metadata:Metadata={title:'Yevhenii · Career Workspace',description:'Журнал пошуку роботи та практика AI-розробки',icons:{icon:'/favicon.svg'}};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="uk"><body>{children}</body></html>;}
