interface Step3ConfirmationProps {
  text?: string;
}

export default function Step3Confirmation({ text }: Step3ConfirmationProps) {
  const response = text?.trim();

  return (
    <article className="panel" style={{ gridColumn: '1 / -1' }}>
      <div className="panel-heading">
        <div><span>STEP 3</span><h2>로봇 대응</h2></div>
      </div>
      <div
        role="status"
        aria-live="polite"
        style={{
          background: '#f8f4f1',
          border: '2px solid #d7c7bd',
          borderRadius: 14,
          padding: 24,
          fontSize: 28,
          fontWeight: 900,
          lineHeight: 1.5,
        }}
      >
        {response || '모델 응답을 받지 못했습니다.'}
      </div>
    </article>
  );
}
