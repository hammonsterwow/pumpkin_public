import { useState } from "react";
import { useCart } from "../context/CartContext";
import { Trash2, Store, CreditCard, ChevronRight } from "lucide-react";
import { Link } from "react-router";
import { motion, AnimatePresence } from "motion/react";

export default function Cart() {
  const { items, removeFromCart, totalPrice } = useCart();
  const [isOrdering, setIsOrdering] = useState(false);

  const handleOrder = () => {
    setIsOrdering(true);
    setTimeout(() => {
      alert("결제가 완료되었습니다! 매장에서 음료를 준비합니다.");
      window.location.href = "/";
    }, 1500);
  };

  return (
    <div className="flex flex-col bg-zinc-50 dark:bg-zinc-950 min-h-full">
      {/* Header */}
      <header className="px-5 pt-6 pb-4 bg-white dark:bg-zinc-950 sticky top-0 z-10 border-b border-zinc-100 dark:border-zinc-800">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-white">장바구니</h1>
      </header>

      {items.length === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 px-5 py-20">
          <div className="w-24 h-24 bg-zinc-100 dark:bg-zinc-900 rounded-full flex items-center justify-center mb-6">
            <Trash2 size={32} className="text-zinc-300 dark:text-zinc-700" />
          </div>
          <p className="text-zinc-500 dark:text-zinc-400 mb-6">장바구니가 비어있습니다.</p>
          <Link 
            to="/order"
            className="px-6 py-3 bg-[#E09D00] text-white font-bold rounded-full shadow-sm hover:bg-[#d69500] transition"
          >
            메뉴 보러가기
          </Link>
        </div>
      ) : (
        <div className="flex-1 pb-40">
          {/* Store Selection */}
          <div className="bg-white dark:bg-zinc-900 p-5 mt-2 border-y border-zinc-100 dark:border-zinc-800">
            <h3 className="text-xs font-semibold text-zinc-500 mb-3">픽업 매장</h3>
            <button className="w-full flex justify-between items-center p-4 rounded-xl border border-[#E09D00] bg-[#E09D00]/5 transition hover:bg-[#E09D00]/10">
              <div className="flex items-center gap-3">
                <Store className="text-[#E09D00]" size={20} />
                <div className="text-left">
                  <p className="font-bold text-zinc-900 dark:text-white text-sm">Kigali Main Store</p>
                  <p className="text-xs text-zinc-500 mt-0.5">현재 위치에서 200m</p>
                </div>
              </div>
              <ChevronRight size={20} className="text-zinc-400" />
            </button>
          </div>

          {/* Cart Items */}
          <div className="mt-2 bg-white dark:bg-zinc-900 border-y border-zinc-100 dark:border-zinc-800">
            <div className="p-5 border-b border-zinc-100 dark:border-zinc-800 flex justify-between items-center">
              <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">주문 메뉴</h3>
              <span className="text-xs text-[#E09D00] font-medium">{items.length}개</span>
            </div>
            
            <ul className="px-5 divide-y divide-zinc-100 dark:divide-zinc-800">
              <AnimatePresence>
                {items.map((item) => (
                  <motion.li 
                    key={item.id}
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="py-4 flex gap-4 overflow-hidden"
                  >
                    <img src={item.image} alt={item.name} className="w-16 h-16 rounded-lg object-cover" />
                    <div className="flex-1">
                      <div className="flex justify-between items-start">
                        <h4 className="font-bold text-zinc-900 dark:text-white text-sm">{item.name}</h4>
                        <button 
                          onClick={() => removeFromCart(item.id)}
                          className="p-1 text-zinc-400 hover:text-red-500 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                      <p className="text-xs text-zinc-500 mt-1">
                        {item.temperature.toUpperCase()} | {item.size} 
                        {item.extraShots > 0 && ` | 샷 추가(${item.extraShots})`}
                      </p>
                      <p className="text-sm font-bold text-zinc-900 dark:text-white mt-2">
                        {item.price.toLocaleString()}원
                      </p>
                    </div>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          </div>

          {/* Payment Method */}
          <div className="bg-white dark:bg-zinc-900 p-5 mt-2 border-y border-zinc-100 dark:border-zinc-800">
            <h3 className="text-xs font-semibold text-zinc-500 mb-3">결제 수단</h3>
            <button className="w-full flex justify-between items-center p-4 rounded-xl border border-zinc-200 dark:border-zinc-700">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center">
                  <CreditCard size={16} className="text-zinc-600 dark:text-zinc-300" />
                </div>
                <div className="text-left">
                  <p className="font-medium text-zinc-900 dark:text-white text-sm">Impactful Pay</p>
                  <p className="text-xs text-[#E09D00] mt-0.5 font-medium">잔액: 15,000원</p>
                </div>
              </div>
              <ChevronRight size={20} className="text-zinc-400" />
            </button>
          </div>
        </div>
      )}

      {/* Checkout Bar */}
      {items.length > 0 && (
        <div className="fixed bottom-[72px] left-0 right-0 mx-auto max-w-[480px] bg-white dark:bg-zinc-900 border-t border-zinc-200 dark:border-zinc-800 p-4 shadow-[0_-10px_20px_rgba(0,0,0,0.05)]">
          <div className="flex justify-between items-center mb-4">
            <span className="text-sm font-medium text-zinc-500">총 결제 금액</span>
            <span className="text-2xl font-bold text-[#E09D00] drop-shadow-sm">
              {totalPrice.toLocaleString()}원
            </span>
          </div>
          <button 
            onClick={handleOrder}
            disabled={isOrdering}
            className="w-full bg-[#E09D00] hover:bg-[#d69500] text-white font-bold py-4 rounded-xl text-lg shadow-sm active:scale-[0.98] transition-all flex justify-center items-center"
          >
            {isOrdering ? (
              <motion.div 
                animate={{ rotate: 360 }} 
                transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
                className="w-6 h-6 border-2 border-black/20 border-t-black rounded-full"
              />
            ) : (
              `${totalPrice.toLocaleString()}원 결제하기`
            )}
          </button>
        </div>
      )}
    </div>
  );
}
