import Image from "next/image";

export default function MaintenancePage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-gray-900 to-gray-950 px-4">
      <div className="text-center max-w-md">
        <Image
          src="/images/logo_mark_rsinsight.svg"
          alt="RSInsight Logo"
          width={80}
          height={80}
          className="mx-auto mb-8"
        />
        
        <div className="mb-6">
          <svg
            className="w-16 h-16 mx-auto text-yellow-500 animate-pulse"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
            />
          </svg>
        </div>

        <h1 className="text-3xl font-bold text-white mb-4">
          We&apos;ll Be Right Back
        </h1>
        
        <p className="text-gray-400 mb-6">
          We&apos;re currently performing scheduled maintenance to bring you new updates and improvements. 
          Please check back shortly.
        </p>

        <p className="text-gray-500 text-sm mt-8">
          Thank you for your patience!
        </p>
      </div>
    </div>
  );
}