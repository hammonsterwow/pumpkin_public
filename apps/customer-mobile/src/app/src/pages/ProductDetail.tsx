import { useState } from "react";
import { useParams, useNavigate } from "react-router";
import { motion } from "motion/react";
import { ChevronLeft, Info, Plus, Minus } from "lucide-react";
import { MENU_DATA } from "../data/menu";
import { useCart } from "../context/CartContext";
import { ImageWithFallback } from "../../components/figma/ImageWithFallback";

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { addToCart } = useCart();
  
  const product = MENU_DATA.find(p => p.id === id);
  
  const [temp, setTemp] = useState<"hot" | "iced">(product?.isIcedOnly ? "iced" : "hot");
  const [size, setSize] = useState<"Tall" | "Grande" | "Venti">("Tall");
  const [extraShots, setExtraShots] = useState(0);

  if (!product) return <div>Product not found</div>;

  const sizePrice = size === "Tall" ? 0 : size === "Grande" ? 500 : 1000;
  const shotPrice = extraShots * 600;
  const totalPrice = product.price + sizePrice + shotPrice;

  const handleAddToCart = () => {
    addToCart({
      productId: product.id,
      name: product.name,
      price: totalPrice,
      image: product.image,
      temperature: temp,
      size,
      extraShots,
      quantity: 1
    });
    navigate(-1);
  };

  return (
    <motion.div 
      initial={{ opacity: 0, x: '100%' }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: '100%' }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      className="flex flex-col bg-white dark:bg-zinc-950 min-h-screen relative"
    >
      {/* Header */}
      <header className="absolute top-0 left-0 right-0 p-4 z-20 flex justify-between items-center">
        <button 
          onClick={() => navigate(-1)}
          className="w-10 h-10 bg-white/80 dark:bg-black/80 backdrop-blur-md rounded-full flex items-center justify-center text-zinc-900 dark:text-white shadow-sm"
        >
          <ChevronLeft size={24} />
        </button>
      </header>

      {/* Product Image Area */}
      <div className="w-full h-[45vh] relative bg-zinc-100 dark:bg-zinc-900">
        <ImageWithFallback 
          src={product.image} 
          alt={product.name} 
          className="w-full h-full object-cover"
        />
        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-white dark:from-zinc-950 to-transparent"></div>
      </div>

      {/* Product Info & Options */}
      <div className="px-6 -mt-10 relative z-10 flex-1 pb-32">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">{product.name}</h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">{product.engName}</p>
        <p className="mt-4 text-sm text-zinc-600 dark:text-zinc-300 leading-relaxed">{product.description}</p>
        
        <div className="h-[1px] w-full bg-zinc-100 dark:bg-zinc-800 my-6"></div>

        {/* Temperature */}
        <section className="mb-6">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-white mb-3">온도</h3>
          <div className="flex gap-2 p-1 bg-zinc-100 dark:bg-zinc-900 rounded-lg">
            {!product.isIcedOnly && (
              <button 
                onClick={() => setTemp("hot")}
                className={`flex-1 py-2.5 rounded-md text-sm font-bold transition-all ${
                  temp === "hot" ? "bg-red-500 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-700"
                }`}
              >
                HOT
              </button>
            )}
            <button 
              onClick={() => setTemp("iced")}
              className={`flex-1 py-2.5 rounded-md text-sm font-bold transition-all ${
                temp === "iced" ? "bg-blue-500 text-white shadow-sm" : "text-zinc-500 hover:text-zinc-700"
              }`}
            >
              ICED
            </button>
          </div>
        </section>

        {/* Size */}
        <section className="mb-6">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">사이즈</h3>
            <span className="text-xs text-zinc-400 flex items-center gap-1"><Info size={12}/> Tall 기준</span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {(["Tall", "Grande", "Venti"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSize(s)}
                className={`py-3 rounded-xl border-2 flex flex-col items-center gap-1 transition-all ${
                  size === s 
                    ? "border-[#E09D00] bg-[#E09D00]/10" 
                    : "border-zinc-100 dark:border-zinc-800 bg-white dark:bg-zinc-900"
                }`}
              >
                <div className={`w-6 h-6 rounded-full border-2 border-current flex items-center justify-center
                  ${s === "Tall" ? "scale-75" : s === "Grande" ? "scale-90" : "scale-100"}
                  ${size === s ? "text-[#E09D00]" : "text-zinc-300 dark:text-zinc-700"}
                `}>
                  <div className="w-1 h-2 bg-current rounded-sm"></div>
                </div>
                <span className={`text-xs font-semibold ${size === s ? "text-[#E09D00]" : "text-zinc-500"}`}>{s}</span>
              </button>
            ))}
          </div>
        </section>

        {/* Extra Options */}
        <section className="mb-6">
          <h3 className="text-sm font-semibold text-zinc-900 dark:text-white mb-3">퍼스널 옵션</h3>
          <div className="flex justify-between items-center py-3 border-b border-zinc-100 dark:border-zinc-800">
            <div>
              <span className="text-sm font-medium text-zinc-900 dark:text-white block">에스프레소 샷 추가</span>
              <span className="text-xs text-zinc-500">+600원</span>
            </div>
            <div className="flex items-center gap-4">
              <button 
                onClick={() => setExtraShots(Math.max(0, extraShots - 1))}
                className="w-8 h-8 rounded-full border border-zinc-200 dark:border-zinc-700 flex items-center justify-center text-zinc-600 dark:text-zinc-300 disabled:opacity-30"
                disabled={extraShots === 0}
              >
                <Minus size={16} />
              </button>
              <span className="w-4 text-center font-semibold">{extraShots}</span>
              <button 
                onClick={() => setExtraShots(Math.min(9, extraShots + 1))}
                className="w-8 h-8 rounded-full border border-zinc-200 dark:border-zinc-700 flex items-center justify-center text-zinc-600 dark:text-zinc-300"
              >
                <Plus size={16} />
              </button>
            </div>
          </div>
        </section>
      </div>

      {/* Fixed Bottom Action */}
      <div className="fixed bottom-0 w-full max-w-[480px] bg-white dark:bg-zinc-950 border-t border-zinc-100 dark:border-zinc-800 p-4 pb-8 z-20 shadow-[0_-10px_40px_rgba(0,0,0,0.05)]">
        <div className="flex justify-between items-center mb-4">
          <span className="text-sm text-zinc-500 font-medium">총 금액</span>
          <span className="text-2xl font-bold text-zinc-900 dark:text-white">
            {totalPrice.toLocaleString()}원
          </span>
        </div>
        <button 
          onClick={handleAddToCart}
          className="w-full bg-[#E09D00] hover:bg-[#d69500] text-white font-bold py-4 rounded-xl text-lg shadow-sm transition-transform active:scale-[0.98]"
        >
          장바구니 담기
        </button>
      </div>
    </motion.div>
  );
}
