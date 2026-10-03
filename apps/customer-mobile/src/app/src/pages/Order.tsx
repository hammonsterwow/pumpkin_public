import { useState } from "react";
import { motion } from "motion/react";
import { Search } from "lucide-react";
import { Link } from "react-router";
import { MENU_DATA } from "../data/menu";

const CATEGORIES = ["전체", "Espresso", "Frappuccino", "Teavana", "Food"];

export default function Order() {
  const [activeCategory, setActiveCategory] = useState("전체");

  const filteredMenu = activeCategory === "전체" 
    ? MENU_DATA 
    : MENU_DATA.filter(item => item.category === activeCategory);

  return (
    <div className="flex flex-col bg-white dark:bg-zinc-950 min-h-full">
      {/* Header */}
      <header className="px-5 pt-6 pb-2 sticky top-0 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-md z-10">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white mb-4">Order</h1>
        
        {/* Search */}
        <div className="relative mb-4">
          <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none">
            <Search size={18} className="text-zinc-400" />
          </div>
          <input 
            type="text" 
            placeholder="메뉴명 검색" 
            className="w-full bg-zinc-100 dark:bg-zinc-900 text-zinc-900 dark:text-white rounded-full py-2.5 pl-10 pr-4 text-sm focus:outline-none focus:ring-2 focus:ring-[#E09D00] transition-all"
          />
        </div>

        {/* Categories */}
        <div className="flex overflow-x-auto no-scrollbar gap-2 pb-2">
          {CATEGORIES.map(category => (
            <button
              key={category}
              onClick={() => setActiveCategory(category)}
              className={`whitespace-nowrap px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                activeCategory === category
                  ? "bg-[#E09D00] text-white"
                  : "bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400"
              }`}
            >
              {category}
            </button>
          ))}
        </div>
      </header>

      {/* Menu List */}
      <div className="px-5 pb-24 pt-2">
        <div className="flex flex-col gap-4">
          {filteredMenu.map((item, i) => (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              key={item.id}
            >
              <Link to={`/product/${item.id}`} className="flex gap-4 p-3 bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-100 dark:border-zinc-800 active:scale-[0.98] transition-transform">
                <img src={item.image} alt={item.name} className="w-20 h-20 rounded-xl object-cover" />
                <div className="flex flex-col justify-center flex-1">
                  <h3 className="font-bold text-zinc-900 dark:text-white text-base">{item.name}</h3>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2">{item.engName}</p>
                  <p className="font-semibold text-zinc-900 dark:text-white">
                    {item.price.toLocaleString()}원
                  </p>
                </div>
              </Link>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
