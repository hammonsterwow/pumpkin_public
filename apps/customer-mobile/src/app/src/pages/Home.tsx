import { motion } from "motion/react";
import { Bell, MapPin, ChevronRight, ScanFace } from "lucide-react";
import { Link } from "react-router";
import { MENU_DATA } from "../data/menu";
import kabochaColor from "figma:asset/a036880becd196a5d2e97bf1f820e1310f4579dc.png";

export default function Home() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col bg-zinc-50 dark:bg-zinc-950 min-h-full"
    >
      {/* Header */}
      <header className="px-5 py-6 flex justify-between items-center bg-white dark:bg-zinc-900 sticky top-0 z-10">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900 dark:text-white">안녕하세요, <span className="text-[#E09D00]">단호박 </span>님</h1>
          <div className="flex items-center gap-1 text-sm text-zinc-500 mt-1">
            <MapPin size={14} className="text-[#E09D00]" />
            <span>이화여대 점</span>
            <ChevronRight size={14} />
          </div>
        </div>
        <button className="relative p-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 transition">
          <Bell size={24} className="text-zinc-700 dark:text-zinc-300" />
          <span className="absolute top-2 right-2.5 w-2 h-2 bg-red-500 rounded-full border border-white dark:border-zinc-900"></span>
        </button>
      </header>

      {/* Quick Order Banner */}
      <div className="px-5 py-4">
        <Link to="/order">
          <div className="bg-[#E09D00] rounded-2xl p-6 relative overflow-hidden flex flex-col justify-center items-start shadow-md transform transition hover:scale-[1.02] active:scale-95">
            <div className="relative z-10 w-2/3">
              <h3 className="text-2xl font-bold text-white leading-tight mb-2">
                다이렉트 오더로<br />빠르게 주문하세요
              </h3>
              <p className="text-white/80 text-sm mb-4">줄 서지 않고 미리 주문하고 픽업!</p>
              <span className="inline-flex items-center justify-center bg-[#1E3826] text-white px-4 py-2 rounded-full text-sm font-bold shadow-sm">
                주문하기
              </span>
            </div>
            {/* Abstract shapes for decoration */}
            <div className="absolute -right-6 -bottom-6 w-32 h-32 bg-white/10 rounded-full blur-2xl"></div>
            <div className="absolute right-[-20px] top-1/2 -translate-y-1/2 w-24 h-24 bg-black/10 rounded-full blur-xl"></div>
          </div>
        </Link>
      </div>

      {/* Face ID Registration Card */}
      <div className="px-5 pb-6">
        <div className="bg-gradient-to-r from-[#1E3826] to-[#2D5036] rounded-2xl p-5 shadow-sm relative overflow-hidden text-white">
          <div className="relative z-10 flex flex-col h-full justify-between">
            <div className="flex justify-between items-start mb-4">
              <div>
                <span className="inline-block px-2 py-1 bg-[#E09D00]/20 text-[#E09D00] text-xs font-bold rounded mb-2">NEW</span>
                <h2 className="text-xl font-bold mb-1">단골 맞춤 서비스 등록</h2>
                <p className="text-sm text-zinc-300">
                  페이스 이미지를 등록하고<br/>
                  매장에서 얼굴 인식으로 특별한 서비스를 경험하세요!
                </p>
              </div>
              <div className="p-3 bg-white/10 rounded-full backdrop-blur-sm">
                <ScanFace size={28} className="text-[#E09D00]" />
              </div>
            </div>
            
            <button className="bg-[#E09D00] hover:bg-[#d69500] text-white text-sm font-bold py-2.5 px-4 rounded-xl transition self-start flex items-center gap-2 mt-2">
              <ScanFace size={16} />
              <span>지금 얼굴 등록하기</span>
            </button>
          </div>
          
          {/* Decorative shapes */}
          <div className="absolute right-[-40px] bottom-[-40px] w-32 h-32 bg-[#E09D00]/20 rounded-full blur-2xl"></div>
          <div className="absolute left-[20%] top-[-20px] w-24 h-24 bg-white/10 rounded-full blur-xl"></div>
        </div>
      </div>

      {/* Menu Section */}
      <div className="px-5 pb-24">
        <div className="flex justify-between items-end mb-4">
          <h3 className="text-lg font-bold text-zinc-900 dark:text-white">추천 메뉴</h3>
          <Link to="/order" className="text-sm font-medium text-zinc-500 hover:text-[#E09D00] transition">
            전체보기
          </Link>
        </div>
        <div className="grid grid-cols-2 gap-4">
          {MENU_DATA.slice(0, 4).map((item) => (
            <Link to={`/product/${item.id}`} key={item.id} className="bg-white dark:bg-zinc-900 rounded-xl overflow-hidden shadow-sm border border-zinc-100 dark:border-zinc-800 transition active:scale-[0.98]">
              <img src={item.image} alt={item.name} className="w-full h-32 object-cover" />
              <div className="p-3">
                <p className="font-bold text-sm text-zinc-900 dark:text-white line-clamp-1">{item.name}</p>
                <p className="text-xs text-zinc-500 font-medium mt-1">{item.price.toLocaleString()}원</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </motion.div>
  );
}