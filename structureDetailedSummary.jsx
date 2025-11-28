import React,{ useMemo } from "react";

const SummaryTable = ({ data }) => {
  const { monthly_summary = [] } = data || {};
  // Extract unique types
  const savingsTypes = useMemo(() => {
    const set = new Set();
    monthly_summary.forEach((m) =>
      m.savings.by_type.forEach((t) => set.add(t.type))
    );
    return Array.from(set);
  }, [monthly_summary]);

  const ventureTypes = useMemo(() => {
    const set = new Set();
    monthly_summary.forEach((m) =>
      m.ventures.by_type.forEach((t) => set.add(t.venture_type))
    );
    return Array.from(set);
  }, [monthly_summary]);

  const loanTypes = useMemo(() => {
    const set = new Set();
    monthly_summary.forEach((m) =>
      m.loans.by_type.forEach((t) => set.add(t.loan_type))
    );
    return Array.from(set);
  }, [monthly_summary]);

  // Calculate running balances
  const runningBalances = useMemo(() => {
    // Initial running totals
    const bal = {
      savings: Object.fromEntries(savingsTypes.map(t => [t, 0])),
      venture: Object.fromEntries(ventureTypes.map(t => [t, 0])),
      loan: Object.fromEntries(loanTypes.map(t => [t, 0]))
    };
  
    // Final accumulated result per month
    const result = { savings: {}, venture: {}, loan: {} };
  
    monthly_summary.forEach(m => {
      const key = m.month;
  
      // ======== SAVINGS ========
      (m.savings?.by_type ?? []).forEach(entry => {
        const type = entry.type;
        const amount = Number(entry.amount) || 0;
  
        bal.savings[type] += amount;
      });
      result.savings[key] = { ...bal.savings };
  
      // ======== VENTURES ========
      (m.ventures?.by_type ?? []).forEach(vt => {
        const type = vt.venture_type;
  
        const deposits = vt.total_venture_deposits;
        const payments = vt.total_venture_payments;
  
        bal.venture[type] += deposits - payments;
      });
      result.venture[key] = { ...bal.venture };
  
      // ======== LOANS ========
      (m.loans?.by_type ?? []).forEach(lt => {
        const type = lt.loan_type;
  
        const disb = lt.total_amount_disbursed;
        const rep = lt.total_amount_repaid;
  
        bal.loan[type] += disb - rep;
      });
      result.loan[key] = { ...bal.loan };
    });
  
    return result;
  }, [monthly_summary, savingsTypes, ventureTypes, loanTypes]);  

  // Format number with 2 decimal places
  const format = (n) =>
    Number(n || 0).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  // Get values for a specific month, section, and type
  const getValue = (month, sec, type) => {
    const m = monthly_summary.find((x) => x.month === month);
    if (!m) {
      return { dep: 0, pay: 0, bal: 0, disb: 0, rep: 0, int: 0, out: 0 };
    }

    if (sec === "savings") {
      const t = m.savings.by_type.find((x) => x.type === type);
      return {
        dep: t?.amount || 0,
        bal: runningBalances.savings[month]?.[type] || 0,
        pay: 0,
        disb: 0,
        rep: 0,
        int: 0,
        out: 0,
      };
    }

    if (sec === "ventures") {
      const t = m.ventures.by_type.find((x) => x.venture_type === type);
      const dep = t?.total_venture_deposits;
      const pay = t?.total_venture_payments;
      return {
        dep,
        pay,
        bal: runningBalances.venture[month]?.[type] || 0,
        disb: 0,
        rep: 0,
        int: 0,
        out: 0,
      };
    }

    if (sec === "loans") {
      const t = m.loans.by_type.find((x) => x.loan_type === type);
      const disb = t?.total_amount_disbursed;
      const rep = t?.total_amount_repaid;
      const int = t?.total_interest_charged;
      const out = t?.total_amount_outstanding || 0;
      return { disb, rep, int, out, dep: 0, pay: 0, bal: 0 };
    }

    return { dep: 0, pay: 0, bal: 0, disb: 0, rep: 0, int: 0, out: 0 };
  };

  if (monthly_summary.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">No data available</div>
    );
  }

  return (
    <div className="w-full overflow-x-auto rounded-md border">
      <table className="w-full text-xs border-collapse">
        <thead>
          {/* Level 1: Section Headers */}
          <tr className="border-b bg-gray-50">
            <th
              rowSpan={3}
              className="relative font-semibold px-3 py-2 w-24 align-bottom border-r"
            >
              <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
                Month
              </span>
            </th>
            <th
              colSpan={savingsTypes.length * 2}
              className="text-center font-semibold border-x px-3 py-2 align-bottom"
            >
              Savings
            </th>
            <th
              colSpan={ventureTypes.length * 3}
              className="text-center font-semibold border-x px-3 py-2 align-bottom"
            >
              Ventures
            </th>
            <th
              colSpan={loanTypes.length * 4}
              className="text-center font-semibold border-x px-3 py-2 align-bottom"
            >
              Loans
            </th>
          </tr>

          {/* Level 2: Type Headers */}
          <tr className="border-b">
            {savingsTypes.map((t) => (
              <th
                key={t}
                colSpan={2}
                className="text-center font-medium px-3 py-1 align-bottom border-r last:border-r-0"
              >
                {t}
              </th>
            ))}
            {ventureTypes.map((t) => (
              <th
                key={t}
                colSpan={3}
                className="text-center font-medium px-3 py-1 align-bottom border-r last:border-r-0"
              >
                {t}
              </th>
            ))}
            {loanTypes.map((t) => (
              <th
                key={t}
                colSpan={4}
                className="text-center font-medium px-3 py-1 align-bottom border-r last:border-r-0"
              >
                {t}
              </th>
            ))}
          </tr>

          {/* Level 3: Column Labels */}
          <tr className="border-b text-gray-600">
            {savingsTypes.flatMap((t) => [
              <th key={`${t}-dep`} className="text-right px-3 py-1">
                Dep
              </th>,
              <th
                key={`${t}-bal`}
                className="text-right px-3 py-1 border-r last:border-r-0"
              >
                Bal
              </th>,
            ])}
            {ventureTypes.flatMap((t) => [
              <th key={`${t}-dep`} className="text-right px-3 py-1">
                Dep
              </th>,
              <th key={`${t}-pay`} className="text-right px-3 py-1">
                Pay
              </th>,
              <th
                key={`${t}-bal`}
                className="text-right px-3 py-1 border-r last:border-r-0"
              >
                Bal
              </th>,
            ])}
            {loanTypes.flatMap((t) => [
              <th key={`${t}-disb`} className="text-right px-3 py-1">
                Disb
              </th>,
              <th key={`${t}-rep`} className="text-right px-3 py-1">
                Rep
              </th>,
              <th key={`${t}-int`} className="text-right px-3 py-1">
                Int
              </th>,
              <th
                key={`${t}-out`}
                className="text-right font-medium px-3 py-1 border-r last:border-r-0"
              >
                Out
              </th>,
            ])}
          </tr>
        </thead>

        <tbody className="divide-y">
          {monthly_summary.map((monthSummary) => {
            const month = monthSummary.month;
            return (
              <tr key={month} className="h-8 hover:bg-gray-50">
                <td className="font-medium text-left px-3 py-1 border-r">
                  {month.split(" ")[0]}
                </td>

                {/* Savings Columns */}
                {savingsTypes.map((savingType) => {
                  const value = getValue(month, "savings", savingType);
                  return (
                    <React.Fragment key={savingType}>
                      <td className="text-right px-3 py-1">{format(value.dep)}</td>
                      <td className="text-right px-3 py-1 border-r last:border-r-0">
                        {format(value.bal)}
                      </td>
                    </React.Fragment>
                  );
                })}

                {/* Ventures Columns */}
                {ventureTypes.map((ventureType) => {
                  const value = getValue(month, "ventures", ventureType);
                  return (
                    <React.Fragment key={ventureType}>
                      <td className="text-right px-3 py-1">{format(value.dep)}</td>
                      <td className="text-right px-3 py-1">{format(value.pay)}</td>
                      <td className="text-right px-3 py-1 border-r last:border-r-0">
                        {format(value.bal)}
                      </td>
                    </React.Fragment>
                  );
                })}

                {/* Loans Columns */}
                {loanTypes.map((loanType) => {
                  const value = getValue(month, "loans", loanType);
                  return (
                    <React.Fragment key={loanType}>
                      <td className="text-right px-3 py-1">{format(value.disb)}</td>
                      <td className="text-right px-3 py-1">{format(value.rep)}</td>
                      <td className="text-right px-3 py-1">{format(value.int)}</td>
                      <td className="text-right font-medium px-3 py-1 border-r last:border-r-0">
                        {format(value.out)}
                      </td>
                    </React.Fragment>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default SummaryTable;
